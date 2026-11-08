import json
import time
import logging
import requests
from functools import wraps
from traceback import format_exc
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Opensea Pending')

class OpenseaPending:
    """
    直接存储图片外链版本
    """
    def __init__(self):
        # self.crypto_scan_job_key = 'crypto:scan:jobs_backup'
        self.num = 0
        self.rds = DataUtils('spider')
        self.table = 'opensea'
        self.redis_cli = redis_cli()
        self.pending_jobs = 'opensea:pending:jobs_backup'
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Length": "2220",
            "Content-Type": "application/json",
            "Dnt": "1",
            "Origin": "https://pro.opensea.io",
            "Referer": "https://pro.opensea.io/",
            "Sec-Ch-Ua": "\"Google Chrome\";v=\"113\", \"Chromium\";v=\"113\", \"Not-A.Brand\";v=\"24\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"macOS\"",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        self.url = 'https://api.pro.opensea.io/analytics/minting/pending'

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
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def req(self, payload):
        """
        发起pending请求
        """
        payload = {'addresses':payload}
        logger.info(f'{self.url}')
        res = requests.post(self.url, json=payload, headers=self.headers, proxies=proxies)
        logger.info(f"{res.status_code} {self.url}")
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        self.parse(res)

    def parse(self, response):
        """
        解析pending数据
        """
        try:
            data = response.json()
        except:
            raise Exception(f'响应体异常 {response.text}')
        all_update_sql_base = 'UPDATE opensea SET numPendingTxs=%s,update_time=now() WHERE collectionAddress=%s'
        update_data = []
        for item in data['data']:
            address = item['address']
            numPendingTxs = item['numPendingTxs']
            update_one_data = (
                numPendingTxs,
                address
            )
            update_data.append(update_one_data)
        if update_data:
            # 入库返回值
            status = self.rds.update_many(all_update_sql_base, update_data)
            # 入库成功记录
            if status:
                logger.info('pending刷新成功')
            else:
                logger.info('pending刷新失败')

    def run(self):
        while True:
            payload = self.redis_cli.spop(self.pending_jobs)
            if payload:
                payload = json.loads(payload)
                payload = payload['payload']
                self.req(payload)
            else:
                logger.info(f'pending 任务为空...')
                time.sleep(60)