from config.exchange import EXCHANGE_WEB_BASE, EXCHANGE_SYMBOL_PARTITION_URL, spot_page_url
import os
import requests
import logging
import time
import ccxt
import datetime
from datetime import datetime,timedelta
from traceback import format_exc
from functools import wraps
from threading import Thread
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('INNO LIST')

class Spider:
    def __init__(self):
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9",
            "apptheme": "dark",
            "content-length": "18",
            "content-type": "application/json;charset=UTF-8",
            "devicelanguage": "zh_CN",
            "dnt": "1",
            "language": "en_US",
            "locale": "en_US",
            "origin": EXCHANGE_WEB_BASE,
            "referer": spot_page_url("JPEGUSDT"),
            "sec-ch-ua": "\"Chromium\";v=\"110\", \"Not A(Brand\";v=\"24\", \"Google Chrome\";v=\"110\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "terminaltype": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        self.data = {"languageType":0}
        self.url = EXCHANGE_SYMBOL_PARTITION_URL
        self.coin_symboltoname_map = {}
        self.redis_cli = redis_cli()
        self.redis_base_starttrader_price = "mainex:startgtrader:price:{}"
        self.redis_marketpairs_key = 'mainex:marketpairs'
        self.redis_base_highestprice = "mainex:highestprice:{}"
        self.highest_marketpairs_map_key = 'mainex:highestamp'
        self.alert_status = False

    def retry(*args):
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
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
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
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def ccxt_get(self, marketPair):
        """
        获取交易所当前10分钟的价格数据
        列表的末尾是最新价
        """
        exchange = getattr(ccxt, 'mainex')({'proxies':proxies})
        # nearly 30m candles
        ohlcv = exchange.fetch_ohlcv(marketPair, limit=30)
        now_price = ohlcv[-1][4]
        now_time = int(ohlcv[-1][0] / 1000)
        max_price_list = []
        for candle in ohlcv:
            price_highest = candle[2]
            max_price_list.append(price_highest)
        max_price = max(max_price_list)
        coinname = marketPair.split('/')[0]
        spider_date = datetime.now().strftime('%Y%m%d')
        # 开盘价
        starttraderprice_key = self.redis_base_starttrader_price.format(coinname)
        starttrader_price = self.redis_cli.get(starttraderprice_key)
        today_now = datetime.now()
        # today_at_0800 = today_now.replace(hour=8, minute=0, second=0)
        today_at_1800 = today_now.replace(hour=18, minute=0, second=0)
        highest_key = self.redis_base_highestprice.format(coinname)
        # 当天第一次运行
        if not starttrader_price:
            max_increased_amp = 0
            # 设定当天的开盘价
            self.redis_cli.set(starttraderprice_key,now_price)
            starttrader_price = now_price
            # 初始化当日最高价
            highest_price = now_price
            self.redis_cli.set(highest_key,highest_price)
            # 初始化告警状态
            self.alert_status = False
        else:
            starttrader_price = float(starttrader_price)
            highest_price = float(self.redis_cli.get(highest_key))
            # 刷新redis当日最高价
            if max_price > highest_price:
                self.redis_cli.set(highest_key, max_price)
                highest_price = max_price
            # 当天最高涨幅
            max_increased_amp = round(((highest_price-starttrader_price)/starttrader_price)*100,1)
        content = f"""
        日期：{spider_date}
        代币简称: {coinname}
        代币当天开盘价: {starttrader_price}
        代币当天最高价:  {highest_price}
        代币当天最高涨幅: {max_increased_amp}%
        """
        logger.info(content)
        # 刷新redis币对的最高涨幅
        max_increased_amp_comefromredis = self.redis_cli.hget(self.highest_marketpairs_map_key,coinname)
        if max_increased_amp_comefromredis:
            max_increased_amp_comefromredis = float(max_increased_amp_comefromredis)
            if max_increased_amp > max_increased_amp_comefromredis:
                self.redis_cli.hset(self.highest_marketpairs_map_key,coinname,max_increased_amp)
        else:
            self.redis_cli.hset(self.highest_marketpairs_map_key, coinname, max_increased_amp)
        self.alert()

    def alert(self):
        today_now = datetime.now()
        today_at_1700 = today_now.replace(hour=17, minute=0, second=0)
        today_at_1730 = today_now.replace(hour=17, minute=30, second=0)
        if today_at_1700 <= today_now < today_at_1730:
            if not self.alert_status:
                content = ''
                self.alert_status = True
                all_redis_highest_amp = self.redis_cli.hgetall(self.highest_marketpairs_map_key)
                for key in all_redis_highest_amp:
                    all_redis_highest_amp[key] = float(all_redis_highest_amp[key])
                list_data = sorted(all_redis_highest_amp.items(), key=lambda kv: (kv[1], kv[0]))
                list_data = list(reversed(list_data))
                num = 0
                for item in list_data:
                    # 过滤AI这个币
                    if item[0] == 'AI':
                        continue
                    # 前五
                    if num > 4:
                        break
                    row = f"{item[0]} 最高涨幅 {item[1]}%\n"
                    content += row
                    num += 1
                webhook_api = os.getenv('LARK_WEBHOOK_MAINEX_2', '')
                title = '涨幅榜'
                sender(content,url=webhook_api,title=title)

    def run(self):
        """
        start entrance
        """
        marketpairs = self.redis_cli.hkeys(self.redis_marketpairs_key)
        for m in marketpairs:
            t = Thread(target=self.ccxt_get,args=(m,))
            t.start()

    def schedule_(self):
        while True:
            today_now = datetime.now()
            today_at_0800 = today_now.replace(hour=8, minute=0, second=0)
            today_at_1800 = today_now.replace(hour=18, minute=0, second=0)
            # 工作时间区间内半小时轮一次
            if today_at_0800 <= today_now <= today_at_1800:
                self.run()
                # 半小时跑一次
                time.sleep(30*60)
            # 工作时间外10s轮一次，直到进入工作区间
            else:
                today_now = datetime.now()
                today_at_1800 = today_now.replace(hour=18, minute=20, second=0)
                today_at_1900 = today_now.replace(hour=19, minute=0, second=0)
                # 18：20-19点这个区间初始化 相关数据
                if today_at_1800 < today_now < today_at_1900:
                    # 初始化 redis缓存的涨幅榜；
                    if self.redis_cli.exists(self.highest_marketpairs_map_key):
                        self.redis_cli.delete(self.highest_marketpairs_map_key)
                        logger.info('开盘价初始化成功')
                    # 初始化 化开盘价，为次日的计算做准备
                    marketpairs = self.redis_cli.hkeys(self.redis_marketpairs_key)
                    for m in marketpairs:
                        coinname = m.split('/')[0]
                        starttraderprice_key = self.redis_base_starttrader_price.format(coinname)
                        if self.redis_cli.exists(starttraderprice_key):
                            self.redis_cli.delete(starttraderprice_key)
                            logger.info('开盘价初始化成功')
                time.sleep(10)

