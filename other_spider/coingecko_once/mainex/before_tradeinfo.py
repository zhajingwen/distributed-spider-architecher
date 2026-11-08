from config.exchange import ccxt_exchange
import logging
import time
import json
import ccxt
import os
from retry import retry
from traceback import format_exc
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_search.search import CoingeckSearch
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_coin_market.markets import CoingeckoCoinMarket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mainex Filter Coins')
env = os.environ.get('env')

class MatchCKAndInitial:
    """
    获取历史交易数据前的相关操作
    """
    def __init__(self, market):
        self.redis_cli = redis_cli()
        # hash
        self.namesymbols_key = 'mainex:namesymbols'
        # hash
        self.symbolids_key = 'mainex:symbolids'
        # string 上个季度上币数据的最后一个币
        self.last_coin = 'mainex:lastcoin'
        # hash
        self.idnamess_key = 'mainex:idsnames'
        # hash
        self.symbols_key = f'coingecko_once:{market}:symbols'
        self.market = market

    @retry(tries=6, delay=3)
    def ccxt_one_pair(self, pair, limit, star_time, end_time):
        """
        pair: str 交易对
        limit：int 采集的K线条数  要超出本季度的时间区间
        return: False or 字符串类型的日期
        """
        exchange = ccxt_exchange({'proxies': proxies})
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
        # logger.info(f'{pair} K线条数：{len(ohlcv_data)} 最早一根K线时间戳：{timestamp}')
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
        # logger.info(f'limit: {limit}')
        # 通过ccxt 判断该币是否是在季度统计内上线的 有值  表示是的
        tartget_coin_status = self.ccxt_one_pair(pair, limit, star_time, end_time)
        return tartget_coin_status

    def get_origin_data(self, start_time, end_time):
        """
        筛选出目标季度的代币
        """
        last_coin = self.redis_cli.get(self.last_coin)
        coin_id = self.redis_cli.hget(self.symbolids_key, last_coin)
        if not coin_id:
            logger.error(f'上个季度末的代币简称有误：{last_coin}')
            return
        all_coins = self.redis_cli.hgetall(self.symbolids_key)
        # mainex ID是递增的，id > coin_id 就说明该币一定是在其后上的
        for symbol in all_coins:
            id = all_coins[symbol]
            if id > coin_id:
                pair = f'{symbol}/USDT'
                status = self.ccxt_judge_target_coin(pair, start_time, end_time)
                if not status:
                    logger.info(f'非统计季度内的币：{pair}')
                    continue
                listing_time = status
                name = self.redis_cli.hget(self.idnamess_key, id)
                data = {
                    'name': name,
                    'symbol': symbol,
                    'pair': pair,
                    'listing_time': listing_time,
                    # 该键值对会激活 coingecko search匹配
                    'coingecko_match':False
                }
                self.redis_cli.hset(self.symbols_key, symbol, json.dumps(data))
                logger.info(data)

    def run(self, start_time, end_time):
        """
        完成coingecko匹配和首发上币打标的工作
        """
        # 匹配操作在服务器完成
        if env != 'local':
            # 防止重复跑补数据的时候，该方法重复执行
            # 也需要注意，当一个新季度开始的时候，需要清空 self.symbols_key 内的数据
            status = self.redis_cli.hgetall(self.symbols_key)
            if not status:
                # 生成季度原始数据
                logger.info('生成季度上币清单')
                self.get_origin_data(start_time, end_time)

            logger.info('与coingecko做匹配并清洗数据')
            # 与coingecko做匹配
            CoingeckSearch(self.market).run()
            logger.info('与coingecko匹配完成，清洗完成')

            # "首发" 特征识别
            CoingeckoCoinMarket(self.market).initial_listing_judge()
        # 生成csv文件在本地完成
        else:
            # 数据写入csv （在开发环境执行）
            # 在CoingeckoCoinMarket().initial_listing_judge() 之后
            CoingeckSearch(self.market).push_data_to_csv()

