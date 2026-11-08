import json
import time
import requests
import os
import logging
from retry import retry
from datetime import datetime
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from .cmc_marketpercent import Cmc
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Marketpercent Main')
env = os.environ.get('env')

class Main:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_jobs = 'mainexmarketpercent:jobs'

        # 用于存放分类后的待告警的数据的key
        self.inner_key_once = 'mainexmarketpercent:marketing:inner:once'
        self.out_key_once = 'mainexmarketpercent:marketing:out:once'
        self.thirdparty_key_once = 'mainexmarketpercent:marketing:thirdparty:once'

        self.base_key = 'mainexmarketpercent:filter:{}'

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers)
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res.json()

    def get_cmc_allcoins(self):
        # 获取CMC能够查到的全部币种信息，通过此来做address匹配拿到slug
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        data = self.req(url)
        return data

    def alert(self, item_list, redis_c, category_type):
        """
        分类+告警
        """
        new_item_list = []
        for item in item_list:
            item = json.loads(item)
            new_item_list.append(item)
        item_list = sorted(new_item_list, key=lambda x: x['rank'])

        for index, item in enumerate(item_list):
            content = item['content']
            url = item['url']
            symbol = item['symbol']
            if index == 0:
                # sender('👇降序排列👇', url, category_type)
                sender('\n', url, category_type)
            alert_status = sender(content, url, symbol)
            key = self.base_key.format(symbol)
            redis_c.setex(key, 60 * 60, 1)
            logger.info(f'{symbol} 已告警 {alert_status}')

    def sorted_alert(self, redis_c):
        """
        分类 + 排序告警
        """
        # Third party做市需要告警的清单
        thirdparty_category = redis_c.smembers(self.thirdparty_key_once)
        if thirdparty_category:
            # 任务执行后初始化初始化
            redis_c.delete(self.thirdparty_key_once)
            # 告警
            self.alert(thirdparty_category, redis_c, '资产部门做市')

        # 内部做市需要告警的清单()
        inner_category = redis_c.smembers(self.inner_key_once)
        if inner_category:
            # 任务执行后初始化初始化
            redis_c.delete(self.inner_key_once)
            # 告警
            self.alert(inner_category, redis_c, 'BG内部做市(ROBIN)')

        # 项目方做市需要告警的清单
        out_category = redis_c.smembers(self.out_key_once)
        if out_category:
            # 任务执行后初始化初始化
            redis_c.delete(self.out_key_once)
            # 告警
            self.alert(out_category, redis_c, '项目方做市')

    def job(self):
        all_coins = self.get_cmc_allcoins()
        rds = DataUtils()
        redis_c = redis_cli()
        # 存放所有任务
        jobs = []
        # 获取redis中的所有任务
        redis_jobs = redis_c.hgetall(self.redis_jobs)
        if redis_jobs:
            for job_key in redis_jobs:
                value = json.loads(redis_jobs[job_key])
                new_job = {
                    'name': job_key,
                    'symbol': value['symbol'],
                    'listing_date': value['listing_date'],
                }
                jobs.append(new_job)
        logger.info(f'共 {len(jobs)} 个任务')
        Cmc().run(jobs, all_coins, rds)
        # 对需要告警的内容进行分类排序告警
        self.sorted_alert(redis_c)

    def run(self):
        if env != 'prod':
            self.job()
        else:
            logger.info(f'程序启动，等待调度中...')
            while True:
                # 每日8：00 - 8：10为可执行时间区间
                today_now = datetime.now()
                # start = today_now.replace(hour=8, minute=0, second=0)
                # end = today_now.replace(hour=8, minute=10, second=0)
                start = today_now.replace(hour=8, minute=50, second=0)
                end = today_now.replace(hour=9, minute=10, second=0)
                if start < today_now < end:
                    logger.info('激活调度')
                    self.job()
                    logger.info('调度结束')
                    time.sleep(60 * 60)
                time.sleep(10)
