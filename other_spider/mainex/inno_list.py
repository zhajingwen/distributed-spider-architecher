from config.exchange import EXCHANGE_SYMBOL_SUFFIX, EXCHANGE_CANDLES_API_URL
import requests
import logging
import time
import os
import datetime
from datetime import datetime
from traceback import format_exc
from functools import wraps
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('INNO LIST')
env = os.environ.get('env')

class Spider:
    def __init__(self):
        # self.data = {"languageType":0}
        # self.coin_symboltoname_map = {}
        self.redis_cli = redis_cli()
        # self.redis_base_starttrader_price = "mainex:startgtrader:price:{}"
        self.redis_marketpairs_key = 'mainex:marketpairs'
        # self.redis_base_highestprice = "mainex:highestprice:{}"
        # self.highest_marketpairs_map_key = 'mainex:highestamp'
        # self.alert_status = False

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
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    def avery_marketpair(self, m, all_redis_highest_amp):
        """
        获取每个交易对的数据
        """
        ohlcv = self.get_mainex(m)
        # 可能为空
        if not ohlcv:
            return
        yesterday_open = ohlcv[0][1]
        today_open = ohlcv[-1][1]
        # open = ohlcv[0][1]
        # max_prices = []
        # for p_l in ohlcv:
        #     max_prices.append(p_l[2])
        # max_price = max(max_prices)
        # diff = (max_price - open) / open
        # logger.info(f'币 {m} 开盘价 {open} 最高价 {max_price}')
        diff = (today_open - yesterday_open) / yesterday_open
        logger.info(f'币 {m} 8：00 价格：{today_open}')
        all_redis_highest_amp[m] = diff * 100


    def marketpairs_data(self):
        """
        所有币对的数据
        """
        marketpairs = self.redis_cli.hkeys(self.redis_marketpairs_key)
        all_redis_highest_amp = {}
        ts = []
        for m in marketpairs:
            t = Thread(target=self.avery_marketpair,args=(m,all_redis_highest_amp,))
            t.start()
            ts.append(t)
        for t in ts:
            t.join()
        logger.info(f'increased list: {all_redis_highest_amp}')
        list_data = sorted(all_redis_highest_amp.items(), key=lambda kv: (kv[1], kv[0]))
        list_data = list(reversed(list_data))
        self.content(list_data)

    @retry()
    def get_mainex(self, symbol):
        """
        官方接口获取数据
        币种清单中有很多币并不存在，这点很奇怪
        """
        _symbol = "".join(symbol.split('/')) + EXCHANGE_SYMBOL_SUFFIX
        url = EXCHANGE_CANDLES_API_URL
        # 前一日的8:00 - 今日8：00
        # 8点对应的精准价格的差值算涨幅
        params_tmp = {
            'symbol': _symbol,
            'period': '1h',
            # 'after': '1678834800000',
            'before': f'{int(time.time())*1000}',
            'limit': 25
        }
        # 开发环境调试
        if env == 'local':
            r = requests.get(url, params_tmp)
            time.sleep(3)
        else:
            r = requests.get(url, params_tmp, proxies=proxies)
        if r.status_code != 200:
            logger.warning(f'{symbol} code error：{r.status_code}')
            return
            # raise Exception(f'{symbol} code error：{r.status_code}')
        try:
            r.json()
        except:
            logger.warning(f'{symbol} josn error：{r.text}')
            return
        if not r.json():
            # raise Exception(f'{symbol} json() None error')
            logger.warning(f'{symbol} json() None error')
            return
        candles = [
            [int(x['ts']), float(x['open']), float(x['high']), float(x['low']), float(x['close']), float(x['usdtVol'])]
            for x in r.json()['data']]
        if not candles:
            logger.warning(f'{symbol} 为空')
        return candles

    def content(self, list_data):
        """
        组合报警内容
        top 10
        """
        num = 0
        content = ''
        for item in list_data:
            name = item[0].split('/')[0]
            diff = round(item[1],1)
            # 过滤AI这个币
            if name == 'AI':
                continue
            # 前10
            if num > 9:
                break
            row = f"{name} 涨幅 {diff}%\n"
            content += row
            num += 1
        logger.info(content)
        webhook_api = os.getenv('LARK_WEBHOOK_MAINEX_2', '')
        title = '涨幅榜'
        sender(content, url=webhook_api, title=title)

    def run(self):
        """
        入口
        """
        if env == 'prod':
            while True:
                today_now = datetime.now()
                today_at_1710 = today_now.replace(hour=8, minute=10, second=0)
                today_at_1711 = today_now.replace(hour=8, minute=11, second=0)
                # 每日08：10分报警
                if today_at_1710 < today_now < today_at_1711:
                    self.marketpairs_data()
                    logger.info('告警成功')
                    time.sleep(30*60)
                else:
                    time.sleep(30)
        else:
            self.marketpairs_data()
            #     logger.info('等待调度中...')