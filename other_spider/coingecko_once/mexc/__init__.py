import os
import datetime
import logging
from .announce import Spider as MexcSpider
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_search.search import CoingeckSearch
from other_spider.coingecko_once.match_ck_and_initial_listing.coingecko_coin_market.markets import CoingeckoCoinMarket
from other_spider.coingecko_once.spider_tradeinfo_from_redis import Spider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TradeInfo Get Before')
env = os.environ.get('env')

def match(start_timestamp, end_timestamp):
    # 涉及到爬虫部分全部在线上执行
    if env != 'local':

        # 抹茶通过上币公告，拿到上币清单
        logger.info('从公告中解析上币信息')
        # 从上币公告拿上币信息
        MexcSpider().run(start_timestamp, end_timestamp)
        logger.info('公告中的上币信息已经存入 coingecko_once:mexc:symbols')

        logger.info('与coingecko做匹配并清洗数据')
        # 与coingecko做匹配
        CoingeckSearch('mexc').run()
        logger.info('与coingecko匹配完成，清洗完成')

        # "首发" 特征识别
        CoingeckoCoinMarket('mexc').initial_listing_judge()
    # 在线上执行完毕后，执行该操作导出数据给分析师校验
    else:
        # 数据写入csv （在开发环境执行）
        # 在CoingeckoCoinMarket().initial_listing_judge() 之后
        CoingeckSearch('mexc').push_data_to_csv()


def mexc_main(spider_name):
    if 'tradeinfo' not in spider_name:
        # 由于上币公告早于上币时间，为了防止漏数据，开始时间提前到6.20号，通常上币公告只会比上币时间早3小时左右，但是个别会提前5天左右
        # 季度开始时间再往前推10天(11.20)
        start_timestamp = 1700409600
        # 2024年1月1号0点
        end_timestamp = 1704038400
        # 除了交易数据以外的所有数据组装
        match(start_timestamp, end_timestamp)
    # MEXC 上币的清单的历史交易数据
    else:
        # 历史数据
        # 根据各个交易所上币清单 请求coingeck接口拿到历史交易数据
        today_now = datetime.datetime.now()
        today_now = today_now - datetime.timedelta(days=100)
        # 需要采集的季度，时间范围
        start = today_now.replace(month=10, day=1)
        end = today_now.replace(month=12, day=31)

        Spider('mexc').run(start, end)