import os
import json
import requests
import time
import ccxt
import logging
import math
import gc
from functools import wraps
from traceback import format_exc
from other_spider.cmc.bot.lark_bot import sender
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from threading import Thread

"""筛选出相对于BTC 汇率上涨的币；每5分钟跑一次"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC High Exchange Rate')


class Spider:

    def __init__(self):
        # 满足1和2的过滤条件
        self.list_url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?' \
                        'start={}&limit=100&sortBy=market_cap&sortType=desc&convert=USD,BTC,ETH&' \
                        'cryptoType=all&tagType=all&audited=false&aux=ath,atl,high24h,low24h,' \
                        'num_market_pairs,cmc_rank,date_added,max_supply,circulating_supply,' \
                        'total_supply,volume_7d,volume_30d,self_reported_circulating_supply,' \
                        'self_reported_market_cap'
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7",
            "cache-control": "no-cache",
            "dnt": "1",
            "origin": "https://coinmarketcap.com",
            "platform": "web",
            "referer": "https://coinmarketcap.com/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        # self.web_hook_api = '<LARK_WEBHOOK_CMC_2>'
        # self.web_hook_api = '<LARK_WEBHOOK_ALERT>'
        self.web_hook_api = os.getenv('LARK_WEBHOOK_CMC_4', '')
        self.redis_cli = redis_cli()
        self.black_key_base = 'cmc:black:strong:'
        self.black_key_have_increased_much_base = 'cmc:black:strong:haveincreased:'
        self.binance_symbols = 'cmc:strong:binance:symbols'
        # self.pid_set_key = 'cmc:strong:pid'
        self.exchange_url = 'https://www.binance.com/zh-CN/trade/{}?theme=dark&type=spot'
        # 特殊的币不报警
        self.names_black_list = [
            'TrueUSD','USDD','USDT','USD Coin','Fei USD','Venus USDT','Origin Dollar',
            'USDC','Tether','Ethereum','Ankr Staked ETH','Liquity USD','TNC Coin',
            'Dai','Gemini Dollar','sUSD','Pax Dollar','Dai','Venus USDC','USDJ','USDX [Kava]',
            'cVault.finance','Venus BUSD','Binance USD','Celo Dollar','USTC','PYUSD'
        ]
        # 将报警过的币，推送给热门板块程序做统计
        self.hot_category_jobs = "crypto_hot_category:start_url"

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10

        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            print(error)
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif '响应码错误：408' in error:
                            logger.warning(f'{func.__name__} 响应码错误：408')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res

            return wrapper

        return recive_func

    @retry()
    def req(self, ohlcv_btc, num):
        """
        q,进程间通信队列
        发起请求拿数据
        """
        url = self.list_url.format(num)
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'列表页：{res.status_code}: {url}')
        try:
            cryptoCurrencyList = res.json()['data']['cryptoCurrencyList']
        except:
            raise Exception(f'响应体异常,准备重试...：{res.text} {url}')
        self.parse(res, num, ohlcv_btc)

    def parse(self, response, num, ohlcv_btc):
        """
        解析数据
        读写数据库，计算涨幅
        调用报警模块
        """
        if response.status_code != 200:
            logger.info(f'列表页状态码异常：{response.status_code}')
            raise Exception(f'response status code error: {response.status_code}')
        else:
            cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
            for cryptoCurrency in cryptoCurrencyList:
                # 如果条件url筛选出来的URL有100个，那么并发就是100个，上限是100，有多少算多少；
                t = Thread(target=self.currency_job, args=(cryptoCurrency,ohlcv_btc,))
                t.start()
            # 翻页，一共就只取前2页（zone规定前200）
            # 请求首页的时候才进入翻页的逻辑，避免无限递归
            if num == 1:
                for i in range(1):
                    now_start_num = 1 + 100 * (i + 1)
                    # p = Process(target=self.req, args=(now_start_num,))
                    # p.start()
                    self.req(ohlcv_btc, now_start_num)

    def currency_job(self, cryptoCurrency, ohlcv_btc):
        """
        每个币的子线程job
        正常来讲一次列表能拉出来200条左右的数据
        """
        id = cryptoCurrency['id']
        name = cryptoCurrency['name']
        symbol = cryptoCurrency['symbol']
        slug = cryptoCurrency['slug']
        quotes = cryptoCurrency['quotes']
        # 数据不完整
        if not quotes:
            logger.info(f'{symbol} 没有计价单位')
            return
        # 3小时内强势计数过的，过滤
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{name} {status}')
            return
        # 自定义黑名单
        if name in self.names_black_list:
            return
        if symbol in self.names_black_list:
            return
        # BTC计价的 需要全部大于0
        price_basebtc = quotes[0]
        percentChange7d_basebtc = price_basebtc['percentChange7d']
        # 7天涨幅强于btc，那么才往下执行
        if percentChange7d_basebtc > 0:
            data = {
                'id': id,
                'name':name,
                'symbol': symbol,
                'slug': slug,
                'url': f'https://coinmarketcap.com/currencies/{slug}/'
            }
            # 校验36h、3天、7天、14天
            self.check_more(data, ohlcv_btc)

    @retry()
    def get_cmc_1month(self, data):
        """
        从cmc获取最近1个月的数据，粒度2小时
        """
        if not data:
            return
        id = data['id']
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart?id={id}&range=1M'
        res = requests.get(url,headers=self.headers)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        points = res.json()['data']['points']
        olhcv = []
        for time_s in points:
            price = points[time_s]['v'][0]
            olhcv.append(price)
        return olhcv

    def check_servral_days(self, coin_ohlcv, ohlcv_btc,h):
        """
        时间区间h内涨幅是否同时大于BTC和ETH
        """
        status = True
        # 目标币 h 小时内的涨幅
        start_target_coin = int(-1 - h/2)
        coin_amplitude = (coin_ohlcv[-1] - coin_ohlcv[start_target_coin])/coin_ohlcv[start_target_coin]
        # BTC h 小时内的涨幅
        start_btc = -1 - h
        btc_amplitude = (ohlcv_btc[-1][4]-ohlcv_btc[start_btc][4])/ohlcv_btc[start_btc][4]
        # 近H小时涨幅得大于BTC
        if coin_amplitude < btc_amplitude:
            status = False
        return status

    def check_more(self, data, ohlcv_btc):
        """
        36、72、168、336小时汇率强势
        """
        coin_ohlcv = self.get_cmc_1month(data)
        for h in [36,72,168,336]:
            status = self.check_servral_days(coin_ohlcv, ohlcv_btc,h)
            # 但凡在1-14天内，有一个时间区间弱势，都跳出
            if not status:
                return
        # 告警到lark
        self.alert(data)
        self.push_job_to_hot_categroy(data)

    @retry()
    def refresh_binance(self):
        """
        刷新交易所所有币种信息
        24小时刷新一次
        """
        while True:
            try:
                # 初始化交易所
                binance_exchange = ccxt.binance({
                    'timeout': 15000,
                    'enableRateLimit': True
                })
                data = binance_exchange.load_markets()
                with self.redis_cli.pipeline(transaction=False)as pipe:
                    for key in data:
                        symbol = key.split('/')[0]
                        pipe.sadd(self.binance_symbols,symbol)
                    pipe.execute()
                logger.info(f'binance 全部币种刷新成功')
                time.sleep(24*60*60)
            except:
                raise Exception('交易所币种列表请求失败')

    @retry()
    def ccxt_get(self):
        """
        获取BTC1小时单位的K线数据 1000小时
        """
        exchange = ccxt.binance({'proxies': proxies})
        ohlcv_btc = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=1000)
        return ohlcv_btc

    def push_job_to_hot_categroy(self, data):
        """
        将币推送给热门板块统计程序消费
        """
        slug = data['slug']
        url = f'https://coinmarketcap.com/currencies/{slug}/'
        job = {
            'url': url
        }
        # 将任务推送给"热门板块"程序消费
        self.redis_cli.lpush(self.hot_category_jobs, json.dumps(job))

    def alert(self, data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        Token Name：{data['name']}

        Token Symbol：{data['symbol']}
        
        CMC链接：{data['url']}
        """
        id = data['id']
        # 如果存在，那么就不报警 由于高并发可能导致重复报警，redis去重失效的情况，需要进行二次验证
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{data["name"]}存在于黑名单{status}')
            return
        symbol = data['symbol']
        # 强势持续时间指数
        incr_key = f'cmc:strong:coins:{symbol}'
        self.redis_cli.incr(incr_key)
        # 新增过期时间 防止key无限堆积
        self.redis_cli.expire(incr_key, 7 * 24 * 60 * 60)
        # 强势持续时间指数
        num = self.redis_cli.get(incr_key)
        num = int(num)
        msg += f'\n递增持续时间指数: {num}'
        sender(msg, self.web_hook_api, '强势币')
        # 设置过期时间3h内报过警的就不要报了
        value = '3小时内有过强势记录'
        self.redis_cli.set(key, value, ex=3 * 60 * 60)

    def delete_extra_zero(self, n):
        """
        将价格转换成符合人类观看的类型
        return: str
        """
        if n < 1 and 'e' in str(n):
            x = str(math.exp(n)).replace('1.', '0.')
            return x
        return n

    def run(self):
        # 24小时刷新一次交易所币种信息
        t = Thread(target=self.refresh_binance)
        t.start()
        num = 0
        # 60分钟 跑一次
        while True:
            num += 1
            logger.info(f'循环监控：{num}')
            # BTC ETH数据
            ohlcv_btc = self.ccxt_get()
            if not ohlcv_btc:
                continue
            # 遍历前2页数据（默认排序）
            self.req(ohlcv_btc, 1)
            logger.info('已跑完，等待下次调度')
            time.sleep(60*60)
            # 手动垃圾回收
            gc.collect()
