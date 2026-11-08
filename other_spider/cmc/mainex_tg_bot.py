from config.exchange import EXCHANGE_SPOT_PAGE_TPL
import os
import requests
import time
import ccxt
import logging
from datetime import datetime
from functools import wraps
from traceback import format_exc
from utils.rds import DataUtils
from other_spider.cmc.bot.tg_bot import TGbot
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from threading import Thread
from .filter_strategy.ma_and_pice_1d import Ma
from decimal import *
# from .week_strong import WeekCandle
# from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MONITOR12')


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
        self.redis_cli = redis_cli()
        self.sql_values = []
        self.black_key_base = 'cmc:blacktg:'
        self.tg_bot = TGbot()
        self.quote_url_base = EXCHANGE_SPOT_PAGE_TPL

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
                        logger.error(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.error(f'{func.__name__} ProxyError')
                        elif '响应码错误：408' in error:
                            logger.warning(f'{func.__name__} 响应码错误：408')
                        else:
                            logger.error(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.error('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(20)
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
        logger.info(f'{res.status_code}: {url}')
        self.parse(res)

    def parse(self, response):
        """
        解析数据
        读写数据库，计算涨幅
        调用报警模块
        """
        if response.status_code != 200:
            logger.info(f'列表页状态码异常：{response.status_code}')
            raise Exception(f'response status code error: {response.status_code}')
        else:
            # time_stamp = int(time.time())
            cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
            totalCount = response.json()['data']['totalCount']
            totalCount = int(totalCount)
            logger.info(f'一共{totalCount}个数据')
            # jobs_backup = []
            for cryptoCurrency in cryptoCurrencyList:
                # self.currency_job(cryptoCurrency,time_stamp)
                # 如果条件url筛选出来的URL有100个，那么并发就是100个，上限是100，有多少算多少；
                t = Thread(target=self.currency_job, args=(cryptoCurrency,))
                t.start()
                # jobs_backup.append(t)
            # 翻页
            self.pagenum += 100
            if self.pagenum < totalCount:
                logger.info(f'当前翻页的起始值 {self.pagenum}')
                self.req(self.pagenum)
            else:
                # 当前的请求翻页结束的时候初始化该值
                self.pagenum = 1
                logger.info('翻页结束，初始化翻页计数')

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
            percentChange24h = price['percentChange24h']
            percentChange7d = price['percentChange7d']
            # percentChange30d = price['percentChange30d']
            percentChange1h = price['percentChange1h']
            volume24h = price['volume24h']
        else:
            logger.info(f'{name} 没有USD计价')
            return
        if percentChange1h < 1:
            logger.info(f'{name}1小时涨幅小于1%{percentChange1h}')
            return
        # 如果存在，那么就不报警
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{name}存在于黑名单{status}')
            return
        spider_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cmc_url = f'https://coinmarketcap.com/currencies/{slug}/'
        alert_data = {
            'spider_date': spider_date,
            'name': name,
            'symbol': symbol,
            'diff': '尚未统计，仅仅依赖30日和24小时的条件',
            'percentChange24h': f"{round(percentChange24h, 1)}%",
            'cmc_url': cmc_url,
            'percentChange7d': percentChange7d,
            'id': id
        }

        # 通过cmc 1D接口算均线
        status_ma_and_priceincreased = Ma(id, name).ma_and_priceincreased()
        if status_ma_and_priceincreased:
            # 交易市场正常
            status_m = self.markets_filter(slug, name, id)
            if status_m:
                marketPair = status_m['marketPair']
                market = status_m['market']
                name = status_m['name']
                id = status_m['id']
                # 价格并且满足涨幅要求 且满足ccxt的相关过滤
                status_ccxt = self.ccxt_get(marketPair, market, name, id)
                # 这里的status为{'ohlvc':ohlvc,'price_diff'}
                if status_ccxt:
                    # 报警
                    alert_data['diff'] = status_ccxt['price_diff']
                    alert_data['diff_time'] = status_ccxt['diff_time']
                    alert_data['volume'] = status_ccxt['volume']
                    alert_data['price_usd'] = self.delete_extra_zero(status_ccxt['price_usd'])
                    alert_data['url'] = self.quote_url_base.format(status_ccxt['marketPair'])
                    self.alert(alert_data)

    def delete_extra_zero(self, n):
        """
        将价格转换成符合人类观看的类型
        return: str
        """
        if isinstance(n, int):
            return n
        elif isinstance(n, float):
            if 'e' in str(n):
                n = round(Decimal(n), 10)
            n = str(n).rstrip('0')  # 删除小数点后多余的0
            n = int(n.rstrip('.')) if n.endswith('.') else n  # 只剩小数点直接转int，否则转回float
        return n

    @retry()
    def markets_filter(self, slug, name, id):
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
        try:
            # 交易所列表策略+价格涨幅策略
            status = self.markets_filter_parse(res, name, id)
            return status
        except:
            logger.error(f'{name} {format_exc()}')
            logger.error(f'{name} 交易市场解析异常')
            return False

    def markets_filter_parse(self, res, name, id):
        """
        判断是否存在mainex交易所
        """
        # redis 黑名单key
        key = self.black_key_base + str(id)
        data = res.json()['data']
        marketPairs = data['marketPairs']
        # 所有交易所名字清单
        m_names = []
        # 存放交易对 mainex
        marketPairs_h_b = {}
        # 判断是否存在mainex交易所
        for m in marketPairs:
            # 交易对
            marketPair = m['marketPair']
            exchangeSlug = m['exchangeSlug']
            m_names.append(exchangeSlug)
            # 得存在mainex交易所的
            if exchangeSlug == 'mainex':
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
            return False

    @retry()
    def ccxt_get(self, marketPair, market, name, id):
        """
        通过ccxt请求交易所接口，获取最近10分钟的价格，颗粒度1分钟
        判断行情最近几分钟是否满足涨幅要求
        """
        # key = self.black_key_base + str(id)
        exchange = getattr(ccxt, market)({'proxies':proxies})
        # exchange.load_markets()
        ohlcv = exchange.fetch_ohlcv(marketPair, limit=60)
        now_price = ohlcv[-1][4]
        now_time = int(ohlcv[-1][0] / 1000)
        # 当前价往前推算，看看第几分钟满足大于3%的涨幅
        num = 0
        alert = False
        volume = 0
        # ohlcv 中包含了当前价，计算涨幅应该拿当前价-开盘价往前递推
        for p in list(reversed(ohlcv)):
            num += 1
            # 统计区间累计成交量
            volume += p[-1]
            # 计算涨幅 当前价-开盘价/开盘价
            price_diff = ((now_price - p[1]) / p[1]) * 100
            # 如果 2分钟之内涨幅超过百分之一的也报警
            if (num >= 1 and num < 3):
                if price_diff > 1.5:
                    alert = True
            if alert:
                # 没涨过 且最近30分无大阴线
                if (not self.before_have_increase(ohlcv, num, name)) and \
                        self.K_strong_recent30m(ohlcv, num, name):
                    # 耗时 分钟为单位
                    diff_time = (now_time - int(p[0] / 1000)) / 60
                    # 由于k先数据对包含了当前时间，故得+1
                    diff_time += 1
                    logger.info(f'{name} {diff_time}分钟涨幅 {price_diff}')
                    data = {
                        # 'ohlcv': ohlcv,
                        'price_diff': price_diff,
                        'diff_time': int(diff_time),
                        'volume': volume,
                        'price_usd':now_price,
                        'marketPair': marketPair.replace('/',''),
                    }
                    return data
                else:
                    return False
        return False

    def before_have_increase(self, ohlcv, old_num, name):
        """
        确保前20分钟内没怎么涨，此策略为了规避买在顶点，买在行情末端
        """
        num = 0
        # 是否已经涨过了
        have_increased = False
        # 拿涨速报警统计区间之前的最近一个收盘价为价格基准；
        the_end_price = list(reversed(ohlcv))[old_num+1][4]
        for p in list(reversed(ohlcv)):
            num += 1
            if num > old_num:
                num_diff = num - old_num
                # 计算涨幅 当前价-开盘价/开盘价
                price_diff = ((the_end_price - p[1]) / p[1]) * 100
                # 涨速测试区间前的1-2分钟内如果涨幅超过了1那么就过滤掉
                if (num_diff >= 1 and num_diff < 3):
                    if price_diff > 1:
                        have_increased = True
                # 涨速测试区间前的3-5分钟内如果涨幅超过了1.5那么就过滤掉
                elif (num_diff < 6 and num_diff >= 3):
                    if price_diff > 1.5:
                        have_increased = True
                # 涨速测试区间前的6-10分钟内如果涨幅超过了3那么就过滤掉
                elif num_diff < 11:
                    if price_diff > 2:
                        have_increased = True
                # 涨速测试区间前的10-25分钟内如果涨幅超过了5那么就过滤掉
                elif (num_diff >= 11 and num_diff < 25):
                    if price_diff > 2.5:
                        have_increased = True
                else:
                    if price_diff > 3:
                        have_increased = True
                if have_increased:
                    logger.info(f'{name} 已经涨过了{num_diff}分钟涨幅 {price_diff}')
                    break
        return have_increased

    def K_strong_recent30m(self, ohlcv, old_num, name):
        """
        确定最近30分钟的强弱，最长的1分钟K线不能是阴线，最长的阴线不能币最近统计周期内的K线阳线要长
        如果没有大阴线就返回True
        """
        num = 0
        negative_numbers = []
        positive_numbers = []
        # 涨速统计区间的K线阳线长度列表
        compute_interval_numbers = []
        for p in list(reversed(ohlcv)):
            num += 1
            candle_length = p[4] - p[1]
            if candle_length < 0:
                negative_numbers.append(abs(candle_length))
            else:
                positive_numbers.append(candle_length)
            if num <= old_num:
                if candle_length > 0:
                    compute_interval_numbers.append(candle_length)
        if max(negative_numbers) > max(positive_numbers):
            logger.info(f'{name} 最近30分钟有大阴线')
            return False
        else:
            if max(compute_interval_numbers) > max(negative_numbers):
                return True
            else:
                logger.info(f'{name} 最近30分钟有大阴线')
                return False

    def alert(self, json_data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        时间：{json_data['spider_date']}

        Token Name：{json_data['name']}

        Token Symbol：{json_data['symbol']}

        {json_data['diff_time']}min 上涨幅度：{round(json_data['diff'],2)}%

        24h上涨幅度：{json_data['percentChange24h']}

        Token Price：${json_data['price_usd']}

        7日涨幅：{round(json_data['percentChange7d'],2)}%

        {json_data['diff_time']}min 累计成交量：{json_data['volume']}

        Mainex链接：{json_data['url']}
        """
        id = json_data['id']
        while True:
            try:
                data = {
                    "chat_id": os.getenv("TG_CHAT_ID_TEST", ""),
                    "message_thread_id": 2618,
                }
                self.tg_bot.sender({},self.web_hook_api,msg,data)
                # 设置过期时间7日，7日内报过警的就不要报了
                key = self.black_key_base + str(id)
                value = '1小时内已经告警过了'
                self.redis_cli.set(key, value, ex=1 * 60 * 60)
                break
            except:
                logger.error(f'{json_data["name"]} 发送异常')
                logger.error(f'{json_data["name"]} {format_exc()}')
                logger.error(f'{json_data["name"]} 重试...')
                time.sleep(10)

    def run(self):
        # 30s钟跑一次
        while True:
            self.req()
            time.sleep(30)

