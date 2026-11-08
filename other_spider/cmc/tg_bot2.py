from config.exchange import EXCHANGE_SPOT_PAGE_TPL
import os
import requests
import time
import ccxt
import logging
import math
import queue
from datetime import datetime
from functools import wraps
from traceback import format_exc
from utils.rds import DataUtils
from other_spider.cmc.bot.tg_bot import TGbot
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from decimal import *
from .filter_strategy.ma_and_pice_1d import Ma
from .filter_strategy.ma_1m import Ma1M
from other_spider.cmc.bot.lark_bot import sender
from .filter_strategy.ma_and_price_7d import Price7D

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TG BOT')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class Spider:

    def __init__(self):
        # 满足1和2的过滤条件
        self.base_url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?' \
                        'start={}&limit=100&sortBy=market_cap&sortType=desc&convert=USD,BTC,' \
                        'ETH&cryptoType=all&tagType=all&audited=false&aux=ath,atl,high24h,' \
                        'low24h,num_market_pairs,cmc_rank,date_added,max_supply,' \
                        'circulating_supply,total_supply,volume_7d,volume_30d,self_reported_circulating_supply,' \
                        'self_reported_market_cap&volume24hRange=500000~&marketCapRange=1000000~'

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
            # "x-request-id": "49fe75f8289d4bffa86643a8f0e08f50"
        }
        self.db = DataUtils('spider')
        self.pagenum = 1
        self.web_hook_api = "https://api.telegram.org/bot" + os.getenv('TG_BOT_TOKEN_CMC', '') + "/sendMessage"
        self.web_hook_api_lark = os.getenv('LARK_WEBHOOK_CMC', '')

        self.redis_cli = redis_cli()
        self.sql_values = []
        # self.black_key_base = 'cmc:blacktg:'
        self.black_key_base = 'cmc:black:mainex:'
        self.tg_bot = TGbot()
        self.quote_url_base = EXCHANGE_SPOT_PAGE_TPL
        # 线程数
        self.excutor = MyThreadPoolExecutor(max_workers=40)

    def executor_callback(self, worker):
        """
        线程池回调函数
        """
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            # logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

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
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif 'does not have market symbol' in error:
                            break
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
    def req(self, num=1):
        """
        发起请求拿数据
        """
        url = self.base_url.format(num)
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'列表页：{res.status_code}: {url}')
        try:
            cryptoCurrencyList = res.json()['data']['cryptoCurrencyList']
        except:
            raise Exception(f'响应体异常,准备重试...：{res.text} {url}')
        self.parse(res, num)

    def parse(self, response, num):
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
            totalCount = response.json()['data']['totalCount']
            totalCount = int(totalCount)
            for cryptoCurrency in cryptoCurrencyList:
                # 如果条件url筛选出来的URL有100个，那么并发就是100个，上限是100，有多少算多少；
                # t = Thread(target=self.currency_job, args=(cryptoCurrency,))
                # t.start()
                self.excutor.submit(self.currency_job, cryptoCurrency).add_done_callback(self.executor_callback)
            # 翻页
            # 请求首页的时候才进入翻页的逻辑，避免无限递归
            if num == 1:
                logger.info(f'一共{totalCount}个数据')
                # 大于100条才需要翻页
                if totalCount > 100:
                    # 第一次请求的出事cursor值
                    origin_start_num = 1
                    for i in range(int(totalCount / 100)):
                        now_start_num = origin_start_num + 100 * (i + 1)
                        self.req(now_start_num)
                        # p = Process(target=self.req, args=(now_start_num,))
                        # p.start()

    def currency_job(self, cryptoCurrency):
        """
        每个币的子线程job
        正常来讲一次列表能拉出来200条左右的数据
        """
        id = cryptoCurrency['id']
        name = cryptoCurrency['name']
        symbol = cryptoCurrency['symbol']
        slug = cryptoCurrency['slug']
        prices = cryptoCurrency['quotes']
        if not prices:
            logger.info(f'{name} 没有计价单位')
            return
        # USD计价的
        price = prices[-1]
        if price['name'] == 'USD':
            # float类型转str
            price_usd = str(price['price'])
            # percentChange24h = price['percentChange24h']
            # percentChange7d = price['percentChange7d']
            # percentChange30d = price['percentChange30d']
            percentChange1h = price['percentChange1h']
            volume24h = price['volume24h']
        else:
            logger.info(f'{name} 没有USD计价')
            return
        if percentChange1h < -4:
            logger.info(f'{name}1小时涨幅小于-4%{percentChange1h}')
            return
        # 如果存在，那么就不报警
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{name}存在于黑名单{status}')
            return
        spider_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_data = {
            'spider_date': spider_date,
            'name': name,
            'symbol': symbol,
            'diff': '尚未统计，仅仅依赖30日和24小时的条件',
            # 'percentChange24h': f"{round(percentChange24h, 1)}%",
            # 'percentChange7d': percentChange7d,
            'id': id
        }
        # 交易市场正常
        status_m = self.markets_filter(slug, name, volume24h, id)
        if status_m:
            marketPair = status_m['marketPair']
            market = status_m['market']
            # 通过cmc 1D接口算均线 价格，k线相关数据并在方法内制定规则进行过滤
            # status_ma_and_priceincreased = Ma(id, name).ma_and_priceincreased()
            data_1D = Ma(id, name, 'mainex').ma_and_priceincreased()
            if data_1D:
                # 文本内容， 平均5m k线的长度
                content,normal_5mk_length,trend_99_amp_pricetoma_shockamp = data_1D
                # 小时数据拼接到 content上合并报警
                data_7D = Price7D(id, name, 'mainex').run()
                if not data_7D:
                    return
                # 价格并且满足涨幅要求 且满足ccxt的相关过滤
                status_ccxt = self.ccxt_get(marketPair, market, name, id, normal_5mk_length)
                # 这里的status为{'ohlvc':ohlvc,'price_diff'}
                if status_ccxt:
                    # # 价格振幅是 k线平均长度的5倍 过滤
                    # if status_ccxt['shock_amp_50m'] > (normal_5mk_length*5):
                    #     value = f'{name} ccxt价格振幅大于k线平均长度的4倍{status_ccxt["shock_amp_50m"]}% {normal_5mk_length}%'
                    #     logger.info(value)
                    #     self.redis_cli.set(key, value, ex=5 * 5 * 60)
                    #     return
                    price_diff = status_ccxt['price_diff']
                    price_diff_ave = status_ccxt['price_diff_ave']
                    # 价格平均涨幅不得小于k线的平均长度的40%，否则不够强势
                    if price_diff_ave < normal_5mk_length*0.4:
                        value = f'{name} 价格平均涨幅小于k线的平均长度{price_diff_ave}% {normal_5mk_length}%'
                        logger.info(value)
                        return
                    # 5m price is under 99ma amp if bigger than increased of price filter
                    if trend_99_amp_pricetoma_shockamp < 0:
                        if price_diff < abs(trend_99_amp_pricetoma_shockamp):
                            value = f'{name} 偏离99ma（5m）幅度大于涨幅{trend_99_amp_pricetoma_shockamp}% {price_diff}%'
                            logger.info(value)
                            return
                    content += data_7D
                    # 报警
                    alert_data['diff'] = price_diff
                    alert_data['diff_time'] = status_ccxt['diff_time']
                    alert_data['price_usd'] = self.delete_extra_zero(status_ccxt['price_usd'])
                    alert_data['url'] = self.quote_url_base.format(status_ccxt['marketPair'])
                    # cmc 1D 数据规则计算得到的值
                    alert_data['1Dvalues'] = content
                    alert_data['amplitude_1mx50'] = status_ccxt['shock_amp_50m']
                    alert_data['volume'] = status_ccxt['volume']
                    self.alert(alert_data)

    @retry()
    def markets_filter(self, slug, name, volume24, id):
        """
        调用该币支持的交易所的接口，得到交易所列表数据
        使其满足以下策略：
        - 查询支持哪些交易所，小于10个滤掉，交易所之间行情价差异较大滤掉，
        主流交易所（交易量占比考前的）价差较大的滤掉，说明都没人愿意套利了
        挑出以usdt计价的，成交量超过百分之十的  几个交易所价格之间进行比较，
        查看价格差值，如果超过阈值那么久过滤
        """
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced'
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{name}: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'状态码异常 {res.status_code}')
        try:
            # 交易所列表策略+价格涨幅策略
            status = self.markets_filter_parse(res, name, id)
            return status
        except:
            logger.error(f'{name} {format_exc()}')
            logger.error(f'{name} 交易市场解析异常')
            return

    def markets_filter_parse(self, res, name, id):
        """
        判断是否存在mainex交易所
        """
        # redis 黑名单key
        key = self.black_key_base + str(id)
        data = res.json()['data']
        marketPairs = data['marketPairs']
        # 所有交易所名字清单
        # m_names = []
        # 存放交易对 mainex
        marketPairs_h_b = {}
        # 判断是否存在mainex交易所
        for m in marketPairs:
            # 交易对
            marketPair = m['marketPair']
            exchangeSlug = m['exchangeSlug']
            quoteSymbol = m['quoteSymbol']
            # m_names.append(exchangeSlug)
            # 得存在mainex交易所的
            if exchangeSlug == 'mainex':
                if quoteSymbol in ['USDT']:
                    marketPairs_h_b['mainex'] = marketPair
        if marketPairs_h_b:
            market = 'mainex'
            marketPair = marketPairs_h_b[market]
            res_format = {
                'marketPair':marketPair,
                'market': market,
                'name': name,
                'id': id,
            }
            return res_format
        else:
            logger.info('no mainex market exsist')
            value = f'{int(time.time())}{name}no mainex market exsist'
            self.redis_cli.set(key, value, ex=24 * 60 * 60)
            return

    @retry()
    def ccxt_get(self, marketPair, market, name, id, normal_5mk_length_cmc):
        """
        通过ccxt请求交易所接口，获取最近100分钟的价格，颗粒度1分钟
        判断行情最近几分钟是否满足涨幅要求
        """
        # key = self.black_key_base + str(id)
        exchange = getattr(ccxt, market)({'proxies':proxies})
        # exchange.load_markets()
        ohlcv = exchange.fetch_ohlcv(marketPair, limit=100)
        # 可能是空列表的情况
        if not ohlcv:
            return
        price_1m_status = Ma1M(ohlcv, name, id, 'mainex', normal_5mk_length_cmc).pass_verify()
        if not price_1m_status:
            return
        pass_status_1m, price_diff_ave, price_diff, diff_time, now_price, volume = price_1m_status
        logger.info(f'{name} {diff_time}分钟涨幅 {price_diff}')
        data = {
            'price_diff_ave': price_diff_ave,
            'price_diff': price_diff,
            'diff_time': int(diff_time),
            'price_usd':now_price,
            'marketPair': marketPair.replace('/',''),
            'shock_amp_50m':pass_status_1m,
            'volume':volume
            # 'on_high_amp':on_high_amp,
            # 'amplitude_10m':amplitude_10m
        }
        return data

    def alert(self, json_data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        时间：{json_data['spider_date']}

        Token Name：{json_data['name']}

        Token Symbol：{json_data['symbol']}

        {json_data['diff_time']}min 上涨幅度：{round(json_data['diff'], 2)}%

        Token Price：${json_data['price_usd']}

        Mainex链接：{json_data['url']}

        ccxt 1m 50单位加权振幅：{json_data['amplitude_1mx50']}

        cmc 1D 统计相关数据：{json_data['1Dvalues']}

        成交量：{json_data['volume']}
        """

        id = json_data['id']
        while True:
            try:
                # data = {
                #     "chat_id": os.getenv("TG_CHAT_ID_TEST", ""),
                #     # "parse_mode": "Markdown",
                #     "message_thread_id": 2618,
                #     # 'disable_web_page_preview': True
                # }
                # self.tg_bot.sender({}, self.web_hook_api, msg, data)
                # 设置过期时间7日，7日内报过警的就不要报了
                key = self.black_key_base + str(id)
                value = '1小时内已经告警过了'
                self.redis_cli.set(key, value, ex=1 * 60 * 60)
                sender(msg, self.web_hook_api_lark)
                break
            except:
                logger.error(f'{json_data["name"]} 发送异常')
                logger.error(f'{json_data["name"]} {format_exc()}')
                logger.error(f'{json_data["name"]} 重试...')
                time.sleep(10)

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
        num = 0
        # 30s钟跑一次
        while True:
            num += 1
            logger.info(f'循环监控：{num}')
            self.req()
            time.sleep(30)

