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
logger = logging.getLogger('Opensea Detail')

class DetailPending:
    """
    直接存储图片外链版本
    """
    def __init__(self):
        self.num = 0
        self.rds = DataUtils('spider')
        self.table = 'opensea'
        self.redis_cli = redis_cli()
        self.detail_jobs = 'opensea:detail:jobs_backup'
        self.filter_key = 'opensea:detail:filter'
        self.black_list = 'opensea:detail:blacklist'
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        self.url_base = 'https://pro.opensea.io/_next/data/2640e8d890510d8bf2367fa9606937d9b51d7fbd/en-US/collection/{}.json?slug={}'


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
    def req(self, job):
        """
        发起pending请求
        """
        # 数据库对应的ID 弃用
        collectionSlug = job['collectionSlug']
        # 过滤404黑名单的
        if self.redis_cli.sismember(self.black_list, collectionSlug):
            return
        url = self.url_base.format(collectionSlug, collectionSlug)
        logger.info(f'GET {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        # 如果是404加入黑名单
        if res.status_code == 404:
            self.redis_cli.sadd(self.black_list, collectionSlug)
        logger.info(f"response {res.status_code} {url}")
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        try:
            self.parse(res)
        except:
            logger.info(f'解析异常: {format_exc}')

    def parse(self, response):
        """
        解析pending数据
        """
        try:
            data = response.json()
        except:
            raise Exception(f'响应体异常 {response.text}')

        data = data['pageProps']['dehydratedState']['queries'][0]['state']
        data = data.get('data')
        if not data:
            raise Exception('没有 data')
        # data = data[0]
        twitterUsername = data.get('twitterUsername')
        if not twitterUsername:
            twitterUsername = ''
        discordUrl = data.get('discordUrl')
        if not discordUrl:
            discordUrl = ''
        externalUrl = data.get('externalUrl')
        if not externalUrl:
            externalUrl = ''
        address = data['addresses'][0]['address']
        update_sql = f"update {self.table} set externalUrl={repr(externalUrl)}, discordUrl={repr(discordUrl)}," \
                     f"twitterUsername={repr(twitterUsername)},update_time=now() where collectionAddress={repr(address)};"
        status = self.rds.insert(update_sql)
        if status:
            # 成功后加入去重队列
            self.redis_cli.sadd(self.filter_key,address)
            logger.info(f'{address} 详情补充成功')
        else:
            logger.info(f'{address} 详情补充失败')

    def run(self):
        while True:
            job = self.redis_cli.spop(self.detail_jobs)
            if job:
                job = json.loads(job)
                # 如果 爬过了就不爬了
                address = job['address']
                if self.redis_cli.sismember(self.filter_key, address):
                    continue
                self.req(job)
            else:
                logger.info(f'detail 任务为空...')
                time.sleep(60)