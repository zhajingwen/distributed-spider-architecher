import logging
import os
import time
import requests
from datetime import datetime
from utils.rds import DataUtils
from functools import wraps
from traceback import format_exc
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DAPPRADAR API')
env = os.environ.get('env')

class Spider:
    def __init__(self):
        # self.headers = {"X-BLOBR-KEY": "<DAPPRADAR_BLOBR_KEY>"}
        self.headers = {"X-API-KEY": os.getenv('DAPPRADAR_API_KEY', '')}
        db = 'onchain_data_misc'
        self.table = 'dappradar2'
        self.rds = DataUtils(db)

    def job_rankings(self):
        """
        获取 rankigns 榜单
        """
        jobs = [
            'Arbitrum/all',
            'all/GameFi',
            'all/all',
            'ETH/all',
            'BSC/all',
            'Polygon/all',
            'WAX/all',
            'Solana/all',
            'Optimism/all',
            'Base/all',
            'all/social',
        ]
        jobs_chain_map = {
            'Arbitrum/all': 'arbitrum',
            'all/GameFi': '',
            'all/all': '',
            'ETH/all': 'ethereum',
            'BSC/all': 'bnb-chain',
            'Polygon/all': 'polygon',
            'WAX/all': 'wax',
            'Solana/all': 'solana',
            'Optimism/all': 'optimism',
            'Base/all': 'base',
            'all/social': '',
        }
        for job in jobs:
            job_ = job.strip().split('/')
            chain_ori = job_[0]
            category_ori = job_[1]
            category = category_ori
            chain = jobs_chain_map[job]
            self.list(chain, category, chain_ori, category_ori)

    @retry(tries=3, delay=3)
    def req(self, url, query=None):
        if query:
            response = requests.get(url, headers=self.headers, params=query)
        else:
            response = requests.get(url, headers=self.headers)
        data = response.json()
        return data

    def retrovle_chain(self, chains_list):
        """
        转换公链名称
        """
        chains = {
            "binance-smart-chain": "bsc",
            "zksync-era": "zksync"
        }
        new_chain_list = []
        for c in chains_list:
            if c in chains:
                c = chains[c]
            new_chain_list.append(c)
        # logger.info(new_chain_list)
        if None in new_chain_list:
            new_chain_list.remove(None)
        return new_chain_list

    def list(self, chain, category, chain_ori, category_ori):
        """
        获取rankings排行榜前25名
        """
        if category == 'GameFi':
            category = 'games'
        # url = "https://api.dappradar.com/on-demand/dapps/top/uaw"
        url = 'https://apis.dappradar.com/v2/dapps/top/uaw'
        query = {
            "chain": chain,
            "category": category,
            "range": "24h",
            "top": "25"
        }
        # 部分不指定
        if not chain:
            query.pop('chain')
        if category == 'all':
            query.pop('category')
        logger.info(f'请求列表页：{query}')
        data = self.req(url, query)
        # print(data)
        success = data['success']
        if success:
            results = data['results']
            for index, item in enumerate(results):
                self.parse_rankings(item, chain_ori, category_ori, index+1)
            logger.info(f'列表页请求成功：{query}')
        else:
            logger.error(f'chain: {chain} category: {category} List响应体异常 {data}')

    def parse_rankings(self, item, chain_ori, category_ori, ranking):
        """
        判断social category和其他类别并分别入库
        """
        dappId = item['dappId']
        name = item['name']
        categories = item['categories'][0]
        uaw = item['metrics']['uaw']
        balance = item['metrics']['balance']
        if not balance:
            balance = 'Null'
        chains = self.retrovle_chain(item['chains'])
        uawPercentageChange = item['metrics']['uawPercentageChange']
        volume = item['metrics']['volume']
        volumePercentageChange = item['metrics']['volumePercentageChange']
        chains = str(chains)
        date_ = datetime.now().strftime("%Y-%m-%d")
        if category_ori == 'social':
            chains = self.retrovle_chain(item['chains'])
            if chains:
                chains = ','.join(chains)
            else:
                logger.warning(f'category: social name: {name} {chains}')
                chains = ''
            uawPercentageChange = uawPercentageChange/100
            sql = f"replace INTO dappradar_social VALUES ({repr(name)},{repr(chains)}," \
                  f"{balance},{uaw},{uawPercentageChange},{volume},{volumePercentageChange},{repr(date_)},{int(time.time())});"
        else:
            sql = f"INSERT INTO dappradar2 (`select_chain`, `select_cate`, `rank`, `name`," \
                  f" `category`, `uaw`, `uaw_change`, `date`, `protocols`) VALUES ({repr(chain_ori)}," \
                  f"{repr(category_ori)},{repr(ranking)},{repr(name)},{repr(categories)}," \
                  f"{repr(uaw)},{repr(str(uawPercentageChange)+'%')},{repr(date_)},{repr(chains)});"
        self.rds.insert(sql)
        logger.info(f'rankings {name} inserted')

    def job_nft(self):
        """dappradar NFT数据"""
        # url = 'https://api.dappradar.com/on-demand/nfts/collections?sort=volume'
        url = 'https://apis.dappradar.com/v2/nfts/collections?range=24h&sort=volume&resultsPerPage=25'
        data = self.req(url)
        results_list = data['results']
        for item in results_list:
            collection = item['name']
            chains = item['chains'] #list
            chains = self.retrovle_chain(chains)
            if chains:
                chains = ','.join(chains)
            else:
                logger.warning(f'None chains: {item} {chains}')
                chains = ''
            floorPrice = item['floorPrice'] #float
            if not floorPrice:
                floorPrice = 'Null'
            else:
                floorPrice = round(floorPrice,2)
            avgPrice = item['avgPrice'] #float
            if not avgPrice:
                avgPrice = 'Null'
            else:
                avgPrice = round(avgPrice, 2)
            marketCap = item['marketCap'] #float
            if not marketCap:
                marketCap = 'Null'
            else:
                marketCap = round(marketCap, 2)
            volume = item['volume'] #float
            if not volume:
                volume = 'Null'
            else:
                volume = round(volume, 2)
            volumePercentageChange = item['volumePercentageChange']/100 #float
            if not volumePercentageChange:
                volumePercentageChange = 'Null'
            else:
                volumePercentageChange = round(volumePercentageChange, 2)
            traders = item['traders'] #int
            sales = item['sales'] #int
            update_time = int(time.time())
            date_ = datetime.now().strftime("%Y-%m-%d")

            sql = f"replace INTO dappradar_nft2 VALUES ({repr(collection)}," \
                  f"{repr(chains)},{floorPrice},{avgPrice},{marketCap}," \
                  f"{volume},{volumePercentageChange},{traders},{sales},{update_time},{repr(date_)});"
            self.rds.insert(sql)
            logger.info(f'NFT {collection} inserted')

    def all_jobs(self):
        # rankings榜单数据
        self.job_rankings()
        # NFT榜单（默认）前25 第一页
        self.job_nft()

    def schedule(self):
        """
        定时调度
        """
        while True:
            # 每日7：10分执行
            today_now = datetime.now()
            today_at_07 = today_now.replace(hour=7, minute=0, second=0)
            today_at_07_11  = today_now.replace(hour=7, minute=11, second=0)
            if env == 'prod':
                if today_at_07 < today_now < today_at_07_11:
                    self.all_jobs()
                    logger.info('调度结束')
                    time.sleep(60*60)
            else:
                self.all_jobs()
                logger.info('一次性任务结束')
                break
            time.sleep(10)

    def run(self):
        """启动入口"""
        logger.info('进程启动')
        self.schedule()

if __name__ == '__main__':
    Spider().run()