import time
import requests
import logging
import json
import queue

import re
from copy import deepcopy
from urllib.parse import urlencode
from traceback import format_exc
# from .data_filter import Filter
from other_spider.dexfilter.spiders.retry import retry,retry_net
from threading import Thread
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('USER_A SPIDER')



class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class TradeInfo:
    def __init__(self):
        self.headers = {
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
            'accept': 'application/json, text/plain, */*',
            'dnt': '1',
            'sec-ch-ua-mobile': '?0',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko)',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://dexfilter.com/',
            'accept-encoding': 'gzip',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7'
        }
        # self.filter = Filter()
        self.redis_cli = redis_cli()
        self.redis_tradeinfo_jobkey = 'dexfilter:user_a:tradeinfo'
        self.cookies_store = 'dexfilter:cookies'
        self.excutor = MyThreadPoolExecutor(max_workers=20)
        self.rds = DataUtils('spider')
        self.base_url = 'https://dexfilter.com/v1/{}/getRightTimeInfo?tag={}&dataRange={}'

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hood
        """
        while True:
            cookie_json = self.redis_cli.spop(self.cookies_store)
            if not cookie_json:
                logger.warning('当前没有可调用的cookies,等待...')
                time.sleep(5)
                continue
            cookie_dict = json.loads(cookie_json)
            # cookie超过有效期，那么久重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30*60:
                logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry()
    def req(self, url, cookie_dict):
        """
        common req function
        """
        logger.info(f'request: {url}')
        # {"id": "718fd558da3df70d254df15dc52944f8", "proxy": "<PROXY_URL>", "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36", "cf": "<CF_CLEARANCE>", "timestamp": 1671091997}
        # 以下三项均来自rpc
        self.headers['user-agent'] = cookie_dict['ua']
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        res = retry_net(cookie_dict, url, self.headers, proxies)
        if not res:
            return
        logger.info(f'response code: {res.status_code} {url}')
        # 当响应码异常的时抛出异常让重试装饰器重试
        if (res.status_code == 504) or (res.status_code == 502):
            logger.warning(f'Gateway time-out 重试：{url}')
            raise Exception('504 or 502')
        if res.status_code == '503':
            logger.info(f'当前cookies被封了{cookie_dict} 准备重试...')
            raise Exception('503')
        if res.status_code != 200:
            return
        return res

    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

    def get_all_interval(self, data):
        """
        get different ingterval data about tradeinfo
        """
        chain = data['chain']
        id = data['id']
        all_data = {}
        for i in ['5m','1h','4h','24h']:
            url = self.base_url.format(chain,id,i)
            cookie_dict = self.get_cookie()
            res = self.req(url, cookie_dict)
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
            if not res:
                continue
            all_data[i] = res.json()
        self.parse(all_data, data)

    def parse(self, all_data, data):
        """
        parse the tradeinfo response
        """
        address = data['token']
        # 5m
        newholders_5m = all_data.get('5m',{}).get('data',{}).get('newHolders','null')
        txns_5m = all_data.get('5m',{}).get('data',{}).get('txns','null')
        buys_5m = all_data.get('5m',{}).get('data',{}).get('buys','null')
        sells_5m = all_data.get('5m',{}).get('data',{}).get('sells','null')
        vns_5m = all_data.get('5m',{}).get('data',{}).get('vns','null')
        # 1h
        newholders_1h = all_data.get('1h',{}).get('data',{}).get('newHolders','null')
        txns_1h = all_data.get('1h',{}).get('data',{}).get('txns','null')
        buys_1h = all_data.get('1h',{}).get('data',{}).get('buys','null')
        sells_1h = all_data.get('1h',{}).get('data',{}).get('sells','null')
        vns_1h = all_data.get('1h',{}).get('data',{}).get('vns','null')
        # 4h
        newholders_4h = all_data.get('4h',{}).get('data',{}).get('newHolders','null')
        txns_4h = all_data.get('4h',{}).get('data',{}).get('txns','null')
        buys_4h = all_data.get('4h',{}).get('data',{}).get('buys','null')
        sells_4h = all_data.get('4h',{}).get('data',{}).get('sells','null')
        vns_4h = all_data.get('4h',{}).get('data',{}).get('vns','null')
        # 24h
        newholders_24h = all_data.get('24h',{}).get('data',{}).get('newHolders','null')
        txns_24h = all_data.get('24h',{}).get('data',{}).get('txns','null')
        buys_24h = all_data.get('24h',{}).get('data',{}).get('buys','null')
        sells_24h = all_data.get('24h',{}).get('data',{}).get('sells','null')
        vns_24h = all_data.get('24h',{}).get('data',{}).get('vns','null')
        spider_dat_h = time.strftime("%Y-%m-%d %H", time.localtime(int(time.time())))
        dexfilter_id = data['id']
        sql = f"replace into dexfilter_user_a_b values({repr(address)},{newholders_5m},{txns_5m}," \
              f"{buys_5m},{sells_5m},{vns_5m},{newholders_1h},{txns_1h},{buys_1h}," \
              f"{sells_1h},{vns_1h},{newholders_4h},{txns_4h},{buys_4h},{sells_4h},{vns_4h}," \
              f"{newholders_24h},{txns_24h},{buys_24h},{sells_24h},{vns_24h},{repr(spider_dat_h)}," \
              f"{repr(dexfilter_id)});"
        self.rds.insert(sql)

    def consumer(self):
        """
        执行当前批次的列表页产生的任务，采集详情
        执行完跳出循环
        """
        num = 0
        while True:
            data = self.redis_cli.spop(self.redis_tradeinfo_jobkey)
            if data:
                data = json.loads(data)
                self.excutor.submit(self.get_all_interval, data).add_done_callback(self.executor_callback)
            else:
                # 每10分钟打印一次日志
                num += 1
                if num % 200 == 0:
                    logger.warning('当前任务执行完毕,等待新任务进来')
                time.sleep(3)

    def create(self):
        self.rds.create_table()