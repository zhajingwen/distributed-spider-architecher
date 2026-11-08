import time
import ccxt
import requests
import logging
import json
# import csv
import os
from utils.redisdb import redis_cli
# from .coingecko_match_filed_clean import Identify
from retry import retry
from math import ceil
from dateutil.parser import parse
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Coin Market')
env = os.environ.get('env')

class CoingeckoCoinMarket:
    def __init__(self, market):
        PROXY_URL = os.getenv('PROXY_URL', '')
        self.proxy = {
            'https':PROXY_URL,
            'http': PROXY_URL
        }
        self.redis_cli = redis_cli()
        self.symbols_key = f'coingecko_once:{market}:symbols'
        self.headers = {
            # 不能加请求头，加了会429，是真的怪啊
            # 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            "accept": "application/json"
        }
        self.api = 'https://api.coingecko.com/api/v3/coins/{}'
        # 目标交易所
        self.target_market = 'MEXC'

    @retry(tries=6, delay=3)
    def ccxt_one_market(self, m, limit, exchanges, black_markets_list, filter_markets):
        """
        m: list 交易所
        limit：int 采集的K线条数
        exchanges：list ccxt支持的全部交易所清单
        black_markets_list：list ccxt不支持的交易所黑名单
        filter_markets：list 用于过滤相同的交易所
        """
        pair = m[0]
        market = m[1]
        initial_listing = True
        # 不能是自己，没必要和自己比对
        if market != self.target_market:
            # market 小写
            market = market.lower()
            if market == 'gate.io':
                market = 'gateio'
            if (market in exchanges) and (market not in black_markets_list):
                # 查询过的交易所就不再查询了，只考虑一个币对；
                if market not in filter_markets:
                    # try:
                    logger.info(f'币：{pair} 交易所：{market} K线条数 发起请求')
                    exchange = getattr(ccxt, market)({'proxies': proxies})
                    timeframe = '1d'
                    ohlcv_data = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
                    logger.info(f'币：{pair} 交易所：{market} K线条数：{len(ohlcv_data)} {self.target_market}条数：{limit - 3}')
                    # 一旦有一个上币时间比 self.target_market 早，那么 self.target_market 就不是首发
                    if len(ohlcv_data) > (limit - 3):
                        initial_listing = False
                    filter_markets.append(market)
                    # except:
                    #     logger.error(f'查不到该交易所：{market}')
            else:
                logger.error(f'该交易所不在ccxt支持的清单中：{market}')
        return initial_listing

    def ccxt_get_day_ohlcv(self, new_new_markets, limit, exchanges):
        """
        new_new_markets：交易所清单
        limit：日K线条数
        exchanges：ccxt支持的交易所清单：['ace', 'alpaca', 'ascendex',,,,,,
        """
        # 不分交易所不支持获取 fetchOHLCV   phemex {"code":30000,"msg":"Please double check in
        black_markets_list = ['indodax','phemex']
        # 一个交易所可能出现在new_new_markets多次，比如：binance CYBER/USDT binance CYBER/TRY
        # 过滤相同交易所
        filter_markets = []
        initial_listing = True
        # new_new_markets
        for m in new_new_markets:
            try:
                initial_listing = self.ccxt_one_market(m, limit, exchanges, black_markets_list, filter_markets)
            except:
                pass
        return initial_listing

    @retry(tries=3, delay=3)
    def req(self, id, num, item, symbol, exchanges):
        """
        根据coingecko ID 发起请求, 拿到上线交易所的清单; 并根据该清单利用ccxt请求交易所ohlv数据，比对 self.target_market 看其是否是首发
        """
        url = self.api.format(id)
        logger.info(f'交易所清单：{num} get: {url}')
        if env == 'local':
            response = requests.get(url, headers=self.headers)
        else:
            response = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{num} response: {response.status_code} {url}')
        if response.status_code == 429:
            time.sleep(3)
            raise Exception('频率过高，重试...')
        if response.status_code == 200:
            data = response.json()
            markets_list = data["tickers"]
            # 统计所有交易所总交易量
            volume_all_market = 0
            new_markets = []
            for market in markets_list:
                market_name = market["market"]["name"]
                base = market["base"]
                # 如果是dex， base是这种类型0XF899E83E6C6DF1A0D4887CF0209193AA97236322
                # 长度42
                if len(base) > 40:
                    # logger.warning(f'{market_name} base异常：{base}')
                    # 如果异常剔除该条数据
                    continue
                target = market["target"]
                pair = f'{base}/{target}'
                volume = market["volume"]
                volume_all_market += volume
                new_markets.append([pair,market_name,volume])
            new_new_markets = []
            for m in new_markets:
                # 百分比
                volume_percent = round((m[-1]/volume_all_market)*100,2)
                m.pop()
                m.append(volume_percent)
                new_new_markets.append(m)
            # 刷新首发上币的状态值
            if len(new_new_markets) > 1:
                Initial_Listing = item.get('Initial_Listing', None)
                # mexc未被解析出来的（从标题解析）再继续解析     非mexc
                if (Initial_Listing == 'no of title') or (Initial_Listing == None):
                    listing_time = item['listing_time']
                    # 如果日期中既没有2023也没有2024，那么就是非法日期
                    if ('2023' not in listing_time) and ('2024' not in listing_time):
                        return
                    # 部分时间会是这种结构，需要清洗
                    # 2023-07-18 09:00 (UTC time, Trading will commence once the deposits meet the minimum liquidity requirements.)
                    if ' (UTC' in listing_time:
                        listing_time = listing_time.split(' (UTC')[0]
                    logger.info(f'listing_time: {listing_time}')
                    dt = parse(listing_time)
                    listing_timestamp = dt.timestamp()
                    time_gap = (int(time.time()) - listing_timestamp)/(24*60*60)
                    # 这个数值就是请求ccxt日线数据最多能拿到的量 time_gap_day 个
                    # 如果别的交易所日线数据大于 time_gap_day 个，那么就说明 self.target_market 不是首发上币
                    time_gap_day = ceil(time_gap)
                    # 再往前推 3 天 留有比对空间
                    limit = time_gap_day + 3
                    # 如果是False认为非首发
                    initial_status = self.ccxt_get_day_ohlcv(new_new_markets, limit, exchanges)
                    item['Initial_Listing'] = initial_status
            # 刷新首发上币的状态值
            else:
                item['Initial_Listing'] = True
            # 将一个币对应的交易所清单组合到原始数据中
            item['markets'] = new_new_markets
            # 更新数据库
            data_update = json.dumps(item)
            self.redis_cli.hset(self.symbols_key, symbol, data_update)

    def initial_listing_judge(self):
        """
        "首发"特征识别（coingecko交易所列表+ccxt）
        通过coingecko 的api 拿到每个币的交易所清单，并更新到原始数据
        """
        # ccxt支持的交易所清单 list ['ace', 'alpaca', 'ascendex']
        exchanges = ccxt.exchanges
        all_data = self.redis_cli.hgetall(self.symbols_key)
        num = 0
        for symbol in all_data:
            orin_data = all_data[symbol]
            item = json.loads(orin_data)
            coingecko_match = item['coingecko_match']
            # coingecko 已收录
            if coingecko_match != '-':
                # 已清洗过 coingecko_match list
                if isinstance(coingecko_match, dict):
                    Initial_Listing = item.get('Initial_Listing')
                    # 抹茶第一次运行的状态
                    if Initial_Listing:
                        # 未被解析出来的（从标题解析） or  未刷新过状态的 再继续解析 （仅限于抹茶有no of title，其他交易所有值，但不是这个值，不影响逻辑判断）
                        if Initial_Listing == 'no of title':
                            num += 1
                            id = coingecko_match['id']
                            self.req(id, num, item, symbol, exchanges)
                        else:
                            logger.info(f'首发状态值已判断，并刷新 {coingecko_match}')
                    # 其他交易所 第一次运行的状态
                    # 当第二次运行的时候会在if中进行过滤，不会重复执行
                    else:
                        num += 1
                        id = coingecko_match['id']
                        self.req(id, num, item, symbol, exchanges)

        logger.info('首发状态值打标完毕')