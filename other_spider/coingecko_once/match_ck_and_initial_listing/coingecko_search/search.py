import requests
import logging
import json
import csv
# import os
from retry import retry
from utils.redisdb import redis_cli
from .coingecko_match_filed_clean import Identify
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Search')

class CoingeckSearch:
    def __init__(self, market):
        self.redis_cli = redis_cli()
        self.symbols_key = f'coingecko_once:{market}:symbols'
        # 参数传入MEXC解析出来的symbol
        self.api = 'https://www.coingecko.com/en/search_v2?query={}'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }
        self.clean_mathed = Identify(market)
        self.market = market

    @retry(tries=3, delay=3)
    def req(self, symbol, num):
        """
        根据symbol发起搜索请求
        """
        if symbol:
            url = self.api.format(symbol)
            logger.info(f'{num} Request: {url}')
            res = requests.get(url, headers=self.headers, proxies=proxies)
            logger.info(f'{num} Response: {res.status_code} {url}')
            if res.status_code == 200:
                data = res.json()
                coins = data['coins']
                items = []
                for coin in coins:
                    coin.pop('thumb')
                    coin.pop('market_cap_rank')
                    items.append(coin)
                return items
            else:
                logger.info(f'响应数据为空：{url}')
                return
        else:
            logger.info(f'symbol为空：{symbol}')
            return

    def push_data_to_csv(self):
        """
        导入到csv文件
        只在开发环境执行，且需要等线上任务跑完后，才能在开发环境跑
        """
        path = f'other_spider/coingecko_once/{self.market}_info_before_trade.csv'
        file_match_coingecko = open(path, 'w', encoding='utf-8-sig', newline='')
        file_success_writer = csv.writer(file_match_coingecko)
        row = [
            '上币公告地址',
            '公告标题',
            'Token全称',
            'Token简称',
            'CG上的Token简称',
            '交易对',
            '上线时间',
            '是否首发',
            'CG--Link',
        ]
        file_success_writer.writerow(row)
        all_data = self.redis_cli.hgetall(self.symbols_key)
        # 搜索到空列表的统计
        # cant_be_searched = 0
        # 网络故障的统计
        net_error_count = 0
        for symbol in all_data:
            item = json.loads(all_data[symbol])
            coingecko_match = item['coingecko_match']
            cg_token_symbol = '-'
            cg_url = '-'
            if coingecko_match == False:
                net_error_count += 1
                logger.info(f'{net_error_count} 网络故障：{item}')
            if isinstance(coingecko_match, dict):
                cg_token_symbol = coingecko_match['symbol']
                cg_url = f"https://www.coingecko.com/en/coins/{coingecko_match['id']}"
                coingecko_match = json.dumps(coingecko_match)
            # logger.info(item)
            listing_time = item['listing_time']
            # 时间截止到日
            listing_time = listing_time.split(' ')[0]
            # 是否首发
            Initial_Listing = item.get('Initial_Listing', '-')
            if Initial_Listing == True:
                Initial_Listing = '是'
            elif Initial_Listing == False:
                Initial_Listing = '否'
            else:
                Initial_Listing = '-'
            # 写入csv文件
            row = [
                item.get('mexc_url',''),
                item.get('mexc_title', ''),
                item['name'],
                item['symbol'],
                cg_token_symbol,
                item['pair'],
                listing_time,
                Initial_Listing,
                cg_url
            ]
            file_success_writer.writerow(row)
        logger.info(f'search匹配数据全部写入csv：{path}')

    def Initial_Listing(self):
        """
        仅针对抹茶生效
        通过 上币公告的标题 判定是否是首发上币
        存在 "Initial Listing" 认为是首发  （含有该特征值的量非常少，约占总量的 4% ）
        刷新 self.symbols_key 的字段维度；新增字段 Initial_Listing ，True表示是首发，'no of title'表示无法从标题判断
        在 clean_mathed.matched_data_clean 后执行
        """
        all_data = self.redis_cli.hgetall(self.symbols_key)
        num = 0
        for symbol in all_data:
            orin_data = all_data[symbol]
            item = json.loads(orin_data)
            # 已经通过K线数据判断过"首发状态了"（防止重新跑的时候，又初始化了）
            if 'markets' in item:
                continue
            # 是抹茶来的数才有这个字段
            mexc_title = item.get('mexc_title', None)
            # 非抹茶数据 不进行操作
            if mexc_title == None:
                continue
            if 'Initial Listing' in mexc_title:
                item['Initial_Listing'] = True
                num += 1
                logger.info(f'{num} 首发上币：{item}')
            else:
                # 表示无法通过title判断
                item['Initial_Listing'] = 'no of title'
            data_update = json.dumps(item)
            self.redis_cli.hset(self.symbols_key, symbol, data_update)
        logger.info('MEXC title 校验首发上币完成，数据已更新')

    def match_coingeck(self):
        """
        获取coingecko匹配数据
        刷新 self.symbols_key 使其value更改为JSON，且新增字段：coingecko_match
        coingecko_match 数据类型：False (网络请求失败，每爬取到)，list：0-N个元素
        """
        all_data = self.redis_cli.hgetall(self.symbols_key)
        num = 0
        # 无法搜索到的币进行统计
        cant_be_searched = 0
        for symbol in all_data:
            num += 1
            # logger.info(symbol, all_data)
            orin_data = all_data[symbol]
            try:
                # list
                orin_data = eval(orin_data)
            except:
                # dict
                orin_data = json.loads(orin_data)
            # row = ['2023-08-05T03:31:30Z', 'https://www.mexc.com/support/articles/17827791509868', 'Voting Result and Listing Arrangement for Kickstarter - SeaPad (SPT)', 'SeaPad ', 'SPT', 'SPT/USDT', '2023-08-05 14:00']

            # 是否需要采集的状态值，为True则采集
            need_to_craw_status = False
            if isinstance(orin_data, list):
                need_to_craw_status = True
            else:
                if 'coingecko_match' in orin_data:
                    coingecko_match = orin_data['coingecko_match']
                    # 网络请求失败
                    if coingecko_match == False:
                        need_to_craw_status = True
            # 已经采集则去重
            if not need_to_craw_status:
                logger.info(f'已经进行过coingecko搜索接口匹配操作：{symbol}')
                continue
            # 开始请求搜索接口获取数据
            try:
                match_coingeck_result = self.req(symbol, num)
                if not match_coingeck_result:
                    cant_be_searched += 1
                    logger.info(f'{cant_be_searched} 无法搜索到该币：{symbol} {orin_data}')
            except:
                logger.error(f'请求失败：{symbol} 网络异常')
                match_coingeck_result = False
            # 第一次是list
            if isinstance(orin_data, list):
                item = {
                    'mexc_url': orin_data[1],
                    'mexc_title': orin_data[2],
                    'name': orin_data[3],
                    'symbol': orin_data[4],
                    'pair': orin_data[5],
                    'listing_time': orin_data[6],
                    'coingecko_match': match_coingeck_result
                }
            else:
                item = orin_data.copy()
                item['coingecko_match'] = match_coingeck_result
            # 将匹配到的 coingeck数据更新到数据库
            # row.append(match_coingeck_result)
            data_update = json.dumps(item)
            self.redis_cli.hset(self.symbols_key, symbol, data_update)
        logger.info('所有symbol 都已请求coingecko search api')

    def clean_listing_time(self):
        """
        清洗格式化listing_time
        共两种情况需要格式化
        """
        all_data = self.redis_cli.hgetall(self.symbols_key)
        num = 0
        for symbol in all_data:
            orin_data = all_data[symbol]
            item = json.loads(orin_data)
            # 抹茶过来的一定会有这个字段，但是其他交易所不一定
            listing_time = item.get('listing_time')
            if not listing_time:
                continue
            # 如果日期中既没有2023也没有2024，那么就是非法日期 将其转换成 -
            if ('2023' not in listing_time) and ('2024' not in listing_time):
                listing_time = '-'
            # 部分时间会是这种结构，需要清洗
            # 2023-07-18 09:00 (UTC time, Trading will commence once the deposits meet the minimum liquidity requirements.)
            if ' (UTC' in listing_time:
                listing_time = listing_time.split(' (UTC')[0]
            # 刷新listing_time
            item['listing_time'] = listing_time
            # 刷新数据库
            data_update = json.dumps(item)
            self.redis_cli.hset(self.symbols_key, symbol, data_update)
        logger.info('MEXC listing_time 已全部刷新')

    def run(self):
        """
        基于self.symbols_key原始上币数据匹配 coingecko
        """
        # 初步匹配coingecko 生成coingecko_match 存入redis
        self.match_coingeck()
        # 清洗整理 coingecko_match 字段
        self.clean_mathed.matched_data_clean()
        # 判断是否是首发上币（通过标题） 仅抹茶生效，其他交易所自动跳过
        self.Initial_Listing()
        # 清洗listingtime 仅限抹茶生效
        self.clean_listing_time()