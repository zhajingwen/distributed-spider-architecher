import json
import requests
import time
import logging
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NO Listing In Mainex')

class Markets:
    def __init__(self):
        """
        初步的过滤条件全部都在请求中参数中过滤了
        """
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7",
            "cache-control": "no-cache",
            "dnt": "1",
            "origin": "https://coinmarketcap.com",
            "platform": "web",
            "referer": "https://coinmarketcap.com/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        # self.pagenum = 1
        self.redis_cli = redis_cli()
        self.job_key = 'noexistinmainex:exporteddone'
        self.done_key = 'noexistinmainex:exporteddone2'
        self.export_key = 'noexistinmainex:exportedjob'

    @retry(tries=3, delay=6)
    def get_markets(self, slug, centerType):
        """
        centerType: cex or dex
        过滤上线mainex的币种
        拿到没有上线mainex 币 的上线的交易所清单
        Return None or str
        """
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType={centerType}&sort=cmc_rank_advanced'

        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'Response {res.status_code}: {url}')
        data = res.json()

        data = data['data']
        marketPairs = data.get('marketPairs')
        if marketPairs:
            exchangeNames = []
            for i in marketPairs:
                exchangeName = i['exchangeName']
                # 防止重复
                if exchangeName not in exchangeNames:
                    exchangeNames.append(exchangeName)
            # 过滤已上线迪拜交易所的代币
            if 'Mainex' in exchangeNames:
                logger.info(f'已上线mainex：{slug}')
                return
            markets = ','.join(exchangeNames)
            return markets
        else:
            logger.info(f'查询到的交易所列表为空：{marketPairs}')
            return '未上线任何交易所'


    def run(self):
        """
        处理输入的消息是合约地址
        """
        num = 0
        while True:
            job = self.redis_cli.spop(self.job_key)
            if not job:
                logger.info('任务已全部消费完')
                break
            if not isinstance(job, dict):
                job = json.loads(job)
            # 备份
            self.redis_cli.sadd(self.done_key, json.dumps(job))
            markets = job.get('markets')
            # 只有 markets不为None的时候，或者不为 未上线任何交易所 的时候
            if markets:
                if markets != '未上线任何交易所':
                    slug = job['slug']
                    for center_type in ['cex', 'dex']:
                        ms = self.get_markets(slug, center_type)
                        if center_type == 'cex':
                            if not ms:
                                continue
                            job['cex'] = ms
                        else:
                            job['dex'] = ms
                    self.redis_cli.sadd(self.export_key, json.dumps(job))

