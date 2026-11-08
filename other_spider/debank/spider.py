# -*- coding: utf-8 -*-
import os
import logging
import queue
import requests
import time
from functools import wraps
from traceback import format_exc
from utils.redisdb import redis_cli
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('debank')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)



class Spider():
    # gen_urls()
    name = 'debank'
    redis_key = f"{name}:start_url"
    # change_ua = True
    # proxy = '<PROXY_URL>'
    # proxy = '<PROXY_URL>'
    # proxy = '<PROXY_URL>'
    # proxy = '<PROXY_URL>'

    # start_urls = []
    # 特殊pipeline
    # custom_settings = {
    #     # 'RETRY_TIMES':1,
    #     'ITEM_PIPELINES': {
    #         "scrapy_spider.ext_pipelines.rds_onchain_data_misc.MysqlPipeline": 100,
    #     }
    # }


    def __init__(self):

        # 线程数
        self.excutor = MyThreadPoolExecutor(max_workers=20)
        self.redis_c = redis_cli()
        # self.proxies = {
        #     'http': self.proxy,
        #     'https': self.proxy
        # }
        # 快代理
        # 隧道域名:端口号
        tunnel = "w582.kdlfps.com:18866"
        # 用户名密码方式
        username = os.getenv('DEBANK_USERNAME', '')
        password = os.getenv('DEBANK_PASSWORD', '')
        self.proxies = {
            "http": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel},
            "https": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel}
        }

        self.ua = UserAgent()
        self.db = DataUtils('spider')



    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            # logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception


    def run(self):
        """写入redis开始请求的队列"""
        # name = 'debank'
        # redis_key = f"{name}:start_url"
        # base_url = 'https://api.debank.com/user?id=0x310f3030e7cc99d9093c5fcd7e8a7fe4cc92b9d9'
        base_url = 'https://api.debank.com/user?id={}'

        addresses = []
        with open('other_spider/debank/origin') as f:
            rows = f.read().strip().split('\n')
            for row in rows:
                addresses.append(row.strip())
        # with redis_c.pipeline(transaction=False) as p:
        for address in addresses:
            if self.redis_c.sismember(f'{self.name}:itemsfilter', address):
                logger.info(f'已入库，过滤该请求：{address}')
                continue


            headers = {
                # "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.9",
                # "Account": "{\"random_at\":1695365437,\"random_id\":\"a3260c2766f945f18ce498efd5f57d28\",\"user_addr\":null}",
                "Dnt": "1",
                "Origin": "https://debank.com",
                "Referer": "https://debank.com/",
                # "Sec-Ch-Ua": "\"Google Chrome\";v=\"117\", \"Not;A=Brand\";v=\"8\", \"Chromium\";v=\"117\"",
                # "Sec-Ch-Ua-Mobile": "?0",
                # "Sec-Ch-Ua-Platform": "\"macOS\"",
                # "Sec-Fetch-Dest": "empty",
                # "Sec-Fetch-Mode": "cors",
                # "Sec-Fetch-Site": "same-site",
                # "Source": "web",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                # "X-Api-Nonce": "<NONCE>",
                # "X-Api-Sign": "<DEBANK_API_SIGN>",
                # "X-Api-Ts": "1695365572",
                # "X-Api-Ver": "v2"
            }
            # headers = {
            #     'User-Agent':self.ua.random
            # }
            headers["User-Agent"] = self.ua.random
            url = base_url.format(address)

            #
            # self.req(url, headers, address)
            self.excutor.submit(self.req, url, headers, address).add_done_callback(self.executor_callback)

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
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'ConnectionRefusedError' in error:
                            logger.warning(f'{func.__name__} ConnectionRefusedErr')
                        elif 'json.decoder.JSONDecodeError' in error:
                            logger.warning(f'{func.__name__} JSONDecodeErr')
                        elif '响应码错误：408' in error:
                            logger.warning(f'{func.__name__} 响应码错误：408')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待1s，否则会把账号打废掉
                        time.sleep(1)
                return res
            return wrapper
        return recive_func

    @retry()
    def req(self, url, headers, address):
        logger.info(f'Req: {url}')
        # response = requests.get(url, headers=headers, proxies=self.proxies, verify=False)
        response = requests.get(url, headers=headers, proxies=self.proxies)
        logger.info(f'Response: {response.status_code} {url}')
        if response.status_code != 200:
            raise Exception(f'响应码错误：{response.status_code} 准备重试...')
        self.parse(response, address)

    def parse(self, response, address):
        data = response.json()
        usd_value = data["data"]["user"]["desc"]["usd_value"]
        Balance = round(usd_value,2)
        sql = f"replace into debank values ({repr(address)},{Balance},now());"
        status = self.db.insert(sql)
        logger.info(f'插入：{status}')
        if status:
            self.redis_c.sadd(f'{self.name}:itemsfilter', address)



