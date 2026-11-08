import os
import requests
import json
import time
import logging
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies
from utils.rds import DataUtils
from traceback import print_exc
from functools import wraps


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GemDetail Spider')


class Detail:
    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://www.gem.xyz",
            "referer": "https://www.gem.xyz/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            # <GEM_API_KEY>
            # <GEM_API_KEY>
            "x-api-key": os.getenv('GEM_API_KEY', '')
        }
        self.url = 'https://api-v2-6.gemlabs.xyz/collections'
        self.data = {"filters":{"address":"0xc6dca8e9c9eb5a7eb68b04a69e63352d5d98695c"},"fields":{"name":1,"marketStats":1,"address":1,"description":1,"imageUrl":1,"indexingStatus":1,"sevenDayVolume":1,"traits":1,"standard":1,"discordUrl":1,"mediumUsername":1,"telegramUrl":1,"twitterUsername":1,"stats":{"floor_price":1},"instagramUsername":1,"revealPercentage":1,"totalSupply":1,"wikiUrl":1,"slug":1,"isVerified":1,"externalUrl":1,"updatedAt":1}}
        self.redis_cli = redis_cli()
        self.job_key = 'gem:jobs_backup'
        self.api_key = 'gem:api_key'
        self.rds = DataUtils('spider')
        self.table = 'gem'
        self.filter = 'gem:filter'

    def consumer(self):
        while True:
            job = self.redis_cli.spop(self.job_key)

            if job:
                if type(job) == bytes:
                    job = job.decode('utf-8')
                status = self.redis_cli.sismember(self.filter,job)
                if not status:
                    self.data['filters']['address'] = job
                    self.req(job)
            else:
                logger.warning('当前没有任务...')
                time.sleep(3)

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        默认重试10次
        """
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
                        logger.error(f'{func.__name__}网络请求失败，重试...')
                        print_exc()
                        retry_num += 1
                        if retry_num > num:
                            logger.error('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(20)
                return res
            return wrapper
        return recive_func

    @retry()
    def req(self, job):
        """
        发起详情页请求
        """
        api_key = self.redis_cli.get(self.api_key)
        self.headers['x-api-key'] = api_key
        res = requests.post(self.url,headers=self.headers,data=json.dumps(self.data),proxies=proxies)
        logger.info(f'{job}: {res.status_code}')
        if res.status_code == 200:
            try:
                self.parse(res)
            except:
                logger.error('解析异常')
                print_exc()
        else:
            logger.error(f'请求异常：{job}')

    def parse(self, response):
        """
        解析
        入库
        """
        data = response.json().get('data')
        if not data:
            raise Exception('没有 data')
        data = data[0]
        twitterUsername = data.get('twitterUsername')
        if not twitterUsername:
            twitterUsername = ''
        discordUrl = data.get('discordUrl')
        if not discordUrl:
            discordUrl = ''
        externalUrl = data.get('externalUrl')
        if not externalUrl:
            externalUrl = ''
        address = data.get('address')
        update_sql = f"update {self.table} set externalUrl={repr(externalUrl)}, discordUrl={repr(discordUrl)}," \
                     f"twitterUsername={repr(twitterUsername)},update_time={int(time.time())} where collectionAddress={repr(address)};"
        self.rds.insert(update_sql)
        # 成功后加入去重队列
        self.redis_cli.sadd(self.filter,address)
        logger.info(f'{address} 详情补充成功')


