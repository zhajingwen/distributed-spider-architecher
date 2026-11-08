import time
import requests
import logging
from retry import retry
import os
from hashlib import md5
from datetime import datetime
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.mainex_marketpercent_bot.refresh_allcoins_marketshare.filter_and_mapcmc import FilterMap

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Marketpercent CMC')
env = os.environ.get('env')

class CmcSpider:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_cli = redis_cli()

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers)
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res.json()

    def insert_data_to_rds(self, marketPairs, job, rds):
        """
        insert marketshare data to rds
        """
        count_num = 0
        rank = None
        # volume_24h = None
        # volumePercent = None
        exchangeNames = []
        # other_markets_info = ''
        # 按市占率重新算，不依据CMC的默认规则
        newmarketPairs = []
        # mainex 的市占率
        mainex_volumePercent = None
        # mainex_volume = None
        for makert in marketPairs:
            exchangeName = makert['exchangeName']
            quoteSymbol = makert['quoteSymbol']

            # rank 算法，交易所去重之后的rank值（比如只算USDT交易对的排名）
            if quoteSymbol != 'USDT':
                continue
            # 防止重复
            if exchangeName not in exchangeNames:
                exchangeNames.append(exchangeName)
            else:
                continue
            # 成交量存在疑问：Reserve data unavailable
            reservesAvailable = makert['reservesAvailable']
            if reservesAvailable == 0:
                continue

            newmarketPairs.append(makert)
            if exchangeName == 'Mainex':
                mainex_volumePercent = round(makert['volumePercent'], 2)
        # 过滤掉未收录 mainex 的数据
        if mainex_volumePercent == None:
            return
        # gen rank num
        newmarketPairs_sorted = sorted(newmarketPairs, key=lambda x: x['volumePercent'], reverse=True)
        for makert in newmarketPairs_sorted:
            # volume_24h = makert['volumeUsd']
            # volumePercent = round(makert['volumePercent'], 2)
            count_num += 1
            exchangeName = makert['exchangeName']
            if exchangeName == 'Mainex':
                rank = count_num
                mainex_volume = makert['volumeUsd']
        if rank:
            # 存入当日状态值
            name = job['name']
            symbol = job['symbol']
            spider_date = datetime.now().strftime("%Y-%m-%d")
            id = md5(f'{name}{symbol}{spider_date}'.encode()).hexdigest()
            insert_sql = f'replace into `mainex_marketpercent` values({repr(id)},{repr(name)},{repr(symbol)},{rank},{mainex_volume},{mainex_volumePercent},{repr(spider_date)},{int(time.time())});'
            rds.insert(insert_sql)
            return True

    def crawl_data_and_insert_to_rds(self, job, rds):
        """
        获取已上线交易所全部列表
        将采集的Marketshare数据落库
        """
        slug = job['slug']
        job_content = ''
        for key in job:
            row = f'{key}: {job[key]}\n'
            job_content += row
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced'
        data = self.req(url)
        data = data['data']
        try:
            numMarketPairs = data['numMarketPairs']
        except:
            logger.error(f'无法解析Response {slug} {job} {data}')
            return 'error'
        marketPairs = data.get('marketPairs')
        if len(marketPairs) > numMarketPairs:
            logger.error(f'一共上线{numMarketPairs}个交易所')
            logger.error(f'本次请求获取到{len(marketPairs)}条数据')
        if marketPairs:
            insert_status = self.insert_data_to_rds(marketPairs, job, rds)
            # cmc没收录，有可能coingecko收录了
            if insert_status:
                return True
            else:
                # no celected in cmc marketing
                return False
        # no celected in cmc marketing
        return False

    def run(self, rds):
        jobs = FilterMap().map_job_tocmc()
        for job in jobs:
            # get data from spider(cmc) and insert them to rds
            self.crawl_data_and_insert_to_rds(job, rds)
