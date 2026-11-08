import logging
import os
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_search.search import CoingeckSearch
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_coin_market.markets import CoingeckoCoinMarket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gate Match Coingecko')
env = os.environ.get('env')

class GateMatchCK:
    """
    gate上币清单与coingecko匹配
    """
    def __init__(self, market):
        self.market = market

    def match(self):
        """
        match + 首发打标 + 生成csv文件
        """
        # 生成csv文件在本地完成
        if env == 'local':
            # 数据写入csv （在开发环境执行，match后执行）
            CoingeckSearch(self.market).push_data_to_csv()
        else:
            # 与coingecko做匹配
            logger.info('与coingecko做匹配并清洗数据')
            CoingeckSearch(self.market).run()
            logger.info('与coingecko匹配完成，清洗完成')
            # "首发" 特征识别
            CoingeckoCoinMarket(self.market).initial_listing_judge()