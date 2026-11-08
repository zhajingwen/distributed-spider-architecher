import requests
import time
import logging
import json
import re
from functools import wraps
from traceback import format_exc
from lxml.etree import HTML
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NSWAP DETAIL')

class Detail:
    def __init__(self):
        self.redis_jobs = 'nswap:jobs_backup'
        self.redis_cli = redis_cli()
        self.base_url = 'https://www.nswap.com/api/v2/raffles/{}'
        self.headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        self.rds = DataUtils('spider')
        self.table = 'nswap_raffles'

    def consumer(self):
        # consumer the coinsadjust from list in redis
        while True:
            job = self.redis_cli.spop(self.redis_jobs)
            if not job:
                logger.info('暂无任务，等待中...')
                time.sleep(10)
            else:
                break
        job = json.loads(job)
        raffle_id = job['raffle_id']
        self.req(raffle_id, job)

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        # logger.info(args)
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
                        logger.info(format_exc)
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
    def req(self, raffle_id, job):
        url = self.base_url.format(raffle_id)
        res = requests.get(url=url,headers=self.headers,proxies=proxies)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            raise Exception('response status_code err')
        try:
            self.parse(res, job)
        except:
            logger.error(format_exc())

    def parse(self, response, job):
        """
        parse the listpage response
        """
        collection = job['name']
        Twitter = job['twitter_followers']
        winners = job['winners']
        countdown = job['schedule_end_time']/1000
        timeArray = time.localtime(countdown)
        countdown = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
        Chain = job['chain']
        if Chain == 1:
            Chain = 'eth'
        res_data = response.json()
        code = res_data['code']
        if code != 200:
            logger.error(f'数据体的状态码异常：{code}')
            return
        website = res_data['data']['website']
        description = res_data['data']['description']
        # tree = HTML(description)
        # description = tree.xpath('//*/text()')
        # description = ','.join(description)
        # print(description)
        pattern = re.compile(r'<[^>]+>', re.S)
        description = re.sub(pattern, '', description)
        mint_time = res_data['data']['mint_time']
        if mint_time == 0:
            mint_date = ''
        elif len(str(mint_time)) > 10:
            mint_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mint_time/1000))
        else:
            mint_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mint_time))
        id = job['raffle_id']
        update_time = int(time.time())
        sql_data = f"({id},{repr(collection)},{Twitter},{winners},{repr(countdown)},{repr(Chain)}," \
                   f"{repr(website)},{repr(description)},{repr(mint_date)},{update_time})"
        sql_base = "replace into {}(id,collection,twitter,winner,countdown,chain," \
                              "website,description,mint_date,update_time) values{};"
        sql = sql_base.format(self.table, sql_data)
        self.rds.insert(sql)

    def run(self):
        """
        the consumer entrance
        """
        # monitor the redis queue
        while True:
            self.consumer()