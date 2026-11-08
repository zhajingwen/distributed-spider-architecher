import requests
import logging
import time
import schedule
import json
import random
import os
from traceback import print_exc
from functools import wraps
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MintFun List')
env = os.environ.get('env')

class List:
    def __init__(self):
        """
        """
        self.headers = {
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        # self.url_base = 'https://mint.fun/api/mintfun/fundrop/leaderboard?address={}&sort=streak&cursor=50'
        self.url_base = 'https://mint.fun/api/mintfun/fundrop/leaderboard?address={}&sort=streak'
        self.addresses = [
            '0x0eC115032A74de4F519D4b4Cfd2FB8b44275949e',
            '0x21b38ce8f71DC083518EdDa2C0D8494c8fc88812',
            '0x064145c2668c0c06DF9A4d9878fDB8682F00eB69',
            '0x8B2a0c8d1A0aC89A24bc9893F2bBD23c19e76E0E',
        ]
        self.detail_jobs = 'mintfun:detailjobs'
        self.redis_cli = redis_cli()
        self.list_jobs = 'mintfun:urls'

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
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
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
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

    @retry(3)
    def req(self, url=None):
        """
        send request
        """
        if not url:
            address = random.choice(self.addresses)
            url = self.url_base.format(address)
        logger.info(f'GET {url}')
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'response {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {url}')
        data = res.json()
        cursor = data['cursor']
        currentAddress = data['currentAddress']['entry']
        leaderboard_ = data['leaderboard']
        items = []
        for item in leaderboard_:
            items.append(item)
        items.append(currentAddress)
        with self.redis_cli.pipeline(transaction=False)as pipe:
            for item in items:
                pipe.sadd(self.detail_jobs,json.dumps(item))
            pipe.execute()
        if cursor:
            address = random.choice(self.addresses)
            url = self.url_base.format(address)
            next_url = url + f'&cursor={cursor}'
            self.redis_cli.sadd(self.list_jobs,next_url)

    def job(self):
        """
        单线程
        """
        num = 1
        self.req()
        while True:
            num += 1
            url = self.redis_cli.spop(self.list_jobs)
            if url:
                self.req(url)
            else:
                logger.info(f'采集完了,共 {num} 页')
                break

    def run(self):
        """
        启动入口 定时调度
        """
        if env != 'prod':
            self.job()
        else:
            # 每天8：00 启动
            schedule.every().day.at("08:00").do(self.job)
            while True:
                schedule.run_pending()
                time.sleep(1)
                # 10分钟一条日志
                if not int(time.time())%600:
                    logger.info('等待调度中...')


