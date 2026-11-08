import requests
import logging
import time
import json
from functools import wraps
from traceback import format_exc
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NSWAP LIST')

class List:
    def __init__(self):
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://www.nswap.com",
            "referer": "https://www.nswap.com/launchpad",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        self.redis_jobs = 'nswap:jobs_backup'
        self.redis_cli = redis_cli()
        self.rds = DataUtils('spider')
        self.table = 'nswap'

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
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
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
    def req(self):
        """
        make a request
        """
        url = 'https://www.nswap.com/api/v2/project/all'
        data = {"page":1,"page_size":99,"sort":2,"sort_direction":1}
        res = requests.post(url,headers=self.headers,json=data,proxies=proxies)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            raise Exception('response status_code err')
        try:
            self.parse(res)
        except:
            logger.error(format_exc())
            raise Exception('parse error')

    def parse(self, response):
        """
        parse the listpage response
        """
        data = response.json()
        # if not data.ge
        code = data.get('code')
        if not code:
            logger.error(f'数据体异常，code：{data}')
            return
        if code != 200:
            logger.error(f'数据体异常，code：{code}')
            return
        result = data['data']['result']
        all_update_sql_base = "replace into {}(id,collection,twitter,discord,pre_sale_date,public_mint_date," \
                              "max_supply,chain,website,description,pre_sale_Mint_price,public_mint_price," \
                              "update_time) values{};"
        sql_values = []
        for job in result:
            sql = self.parse_target_key(job)
            sql_values.append(sql)
        # 多条记录一次性插入
        if sql_values:
            all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
            self.rds.insert(all_update_sql)
    # with self.redis_cli.pipeline(transaction=False) as pipe:
        #     for i in result:
        #         pipe.sadd(self.redis_jobs,json.dumps(i))
        #     pipe.execute()
        # logger.info('全部任务已经插入redis')

    def parse_target_key(self, job):
        """
        get the target key
        """
        project_id = job['project_id']
        collection = job['name']
        Twitter = job['twitter_followers']
        discord = job['discord_followers']

        pre_sale_date = job['pre_sale_info'][0]['sale_start_time'] / 1000
        timeArray_pre = time.localtime(pre_sale_date)
        public_mint_date = job['public_sale_info']['sale_start_time'] / 1000
        timeArray_public = time.localtime(public_mint_date)

        pre_sale_date = time.strftime("%Y-%m-%d %H:%M:%S", timeArray_pre)
        public_mint_date = time.strftime("%Y-%m-%d %H:%M:%S", timeArray_public)
        max_supply = job['max_supply']
        Chain = job['chain']
        if Chain == 1:
            Chain = 'eth'
        website = job['website']
        description = job['description']
        Pre_sale_Mint_price = job['pre_sale_info'][0]['sale_price']['price']
        public_mint_price = job['public_sale_info']['sale_price']['price']
        update_sql = f"({project_id},{repr(collection)},{Twitter},{discord},{repr(pre_sale_date)}," \
                     f"{repr(public_mint_date)},{max_supply},{repr(Chain)},{repr(website)}," \
                     f"{repr(description)},{Pre_sale_Mint_price},{public_mint_price},{int(time.time())})"
        return update_sql

    def run(self):
        """
        schedule entrance
        run every hour
        """
        while True:
            self.req()
            logger.info('1 hour later reschedule ')
            time.sleep(1*60*60)