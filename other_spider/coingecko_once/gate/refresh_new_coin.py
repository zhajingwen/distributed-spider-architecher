import requests
import json
import logging
import os
import time
import ccxt
from retry import retry
from traceback import format_exc
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gateio')
env = os.environ.get('env')

class RefreshNewCoin:
    def __init__(self, market):
        self.redis_cli = redis_cli()
        self.symbols_key = f'coingecko_once:{market}:symbols'

    @retry(tries=6, delay=3)
    def ccxt_one_pair(self, pair, limit, star_time, end_time):
        """
        pair: str 交易对
        limit：int 采集的K线条数  要超出本季度的时间区间
        return: False or 字符串类型的日期
        """
        exchange = ccxt.gate({'proxies': proxies})
        timeframe = '1d'
        try:
            ohlcv_data = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        except:
            error = format_exc()
            # 很多币清单中有，但是实际没上线，这就很怪
            if 'does not have market symbol' in error:
                logger.info(f'没有该币对：{pair}')
                return False
            else:
                raise Exception(error)
        # 最早一更k线对应的日期 是否落在季度内
        # 13位的
        timestamp = ohlcv_data[0][0]/1000
        if (timestamp >= star_time) and (timestamp <= end_time):
            timeArray = time.localtime(timestamp)
            # 使用 strftime 将时间格式化为字符串类型的日期
            listing_time = time.strftime("%Y-%m-%d %H:%M", timeArray)
            return listing_time
        else:
            return False

    def ccxt_judge_target_coin(self, pair, star_time, end_time):
        """
        生成获取K线数据的limit 变量，并请求ccxt
        pair: str 交易对
        star_time：int 本季度开始的1号0点时间对应的时间戳
        return: False or 字符串类型的日期
        """
        days = (int(time.time()) - star_time)/(24*60*60)
        # 为了保险在区间外多加3天，实际上会拿到季度前边界外的多余3天
        limit = int(days) + 3
        # 通过ccxt 判断该币是否是在季度统计内上线的 有值  表示是的
        tartget_coin_status = self.ccxt_one_pair(pair, limit, star_time, end_time)
        return tartget_coin_status

    @retry(tries=5,delay=3)
    def new_listing_coins(self, start_time, end_time):
        """
        gate有新币清单，通过接口获取该清单
        """
        data = {
            "page": 1,
            "coin_type": "new-cryptocurrencies",
            "sort": "",
            "order": "",
            "custom": "",
            "category": "USDT"
        }

        url = 'https://www.gate.io/market_price/get_coin_list'
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.gate.io",
            "Referer": "https://www.gate.io/zh/price/view/new-cryptocurrencies",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }
        logger.info(f'POST {url}')
        # res = requests.post(url, data=data, headers=headers, proxies=proxies)
        res = requests.post(url, data=data, headers=headers)
        logger.info(f'Response {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}，准备重试')
        data = res.json()
        for item in data['data']['data']:
            # = 0 才表示正经上线的
            buy_start_timest = item['buy_start_timest']
            symbol = item['symbol']
            if buy_start_timest != 0:
                logger.info(f'该币尚未上线：{symbol}')
                continue
            # 存在就跳过，不重复刷新
            exsit_status = self.redis_cli.hget(self.symbols_key, symbol)
            if exsit_status:
                continue
            name = item['name']
            pair = f"{item['curr_a']}/{item['curr_b']}"
            status = self.ccxt_judge_target_coin(pair, start_time, end_time)
            if not status:
                logger.info(f'非统计季度内的币：{pair}')
                continue
            listing_time = status
            result = {
                'name': name,
                'symbol': symbol,
                'pair': pair,
                'listing_time': listing_time,
                # 该键值对会激活 coingecko search匹配
                'coingecko_match': False
            }
            self.redis_cli.hset(self.symbols_key, symbol, json.dumps(result))

    def refresh_24H(self, start_time, end_time):
        """
        24小时刷新一次
        """
        num = 0
        while True:
            num += 1
            try:
                self.new_listing_coins(start_time, end_time)
                logger.info(f'{num} 今日已刷新')
                time.sleep(24*60*60)
            except:
                # 等待6小时再重试
                time.sleep(6*60*60)