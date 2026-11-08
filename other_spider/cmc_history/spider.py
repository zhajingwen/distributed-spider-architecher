import time

import requests
import logging
import json
from traceback import format_exc
from functools import wraps
from hashlib import md5
from utils.redisdb import redis_cli
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC HISTORY')

class Spider:
    def __init__(self):
        self.gen_id_api = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest?slug={}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced"
        self.redis_cli = redis_cli()
        self.key = "cmc:history:jobs_backup"
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
        # 时间传10位int数值
        self.history_data_api = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/historical?id={}&convertId=2781&timeStart={}&timeEnd={}'
        self.rds = DataUtils('spider')
        self.table = 'cmc_history'


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
                        logger.error(format_exc())
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
    def req_id(self, job):
        """
        to get the slug fit id
        """
        slug = job['slug']
        url = self.gen_id_api.format(slug)
        res = requests.get(url,headers=self.headers)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            logger.error(f'response code error: {job}')
            return
        id = res.json()['data']['id']
        # get history data
        self.get_history_data(job,id)

    @retry()
    def get_history_data(self, job, id):
        """
        get historical price data
        单次请求智能获取100日的数据（100条）
        """
        start_time = 1654012800
        break_status = None
        while True:
            end_time = start_time + 99*24*60*60
            # maybe cross the line
            if end_time > int(time.time()):
                end_time = int(time.time())
                break_status = True
            url = self.history_data_api.format(id,start_time,end_time)
            res = requests.get(url,headers=self.headers)
            logger.info(f'{res.status_code} {url}')
            self.parse(res, job)
            # exchange the starttime connect to the last end
            start_time = end_time
            # break the loop
            if break_status:
                break



    def parse(self, response, job):
        """
        parse the history data of slug price
        """
        all_update_sql_base = "replace into {}(id,slug,name,symbol,Date,Open,High,Low,Close,Volume,MarketCap) values{};"
        sql_values = []
        data = response.json()['data']['quotes']
        for quote in data:
            time_date = quote['timeOpen'].split('T')[0]
            id = md5(f'{time_date}{job["slug"]}'.encode()).hexdigest()
            quote_data = quote['quote']
            volume = quote_data['volume']
            open = quote_data['open']
            marketCap = quote_data['marketCap']
            low = quote_data['low']
            high = quote_data['high']
            close = quote_data['close']
            one_sql = f'({repr(id)},{repr(job["slug"])},{repr(job["full_name"])},{repr(job["abbreviation"])},' \
                      f'{repr(time_date)},{repr(open)},{repr(high)},{repr(low)},{repr(close)},' \
                      f'{repr(volume)},{repr(marketCap)})'
            sql_values.append(one_sql)
        # 多条记录一次性插入
        if sql_values:
            all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
            self.rds.insert(all_update_sql)
            logger.info('insert successfully')

    def create_table(self):
        self.rds.create_table()





    def consumer(self):
        while True:
            try:
                jobs = self.redis_cli.hgetall(self.key)
                break
            except:
                logger.error('redis connection error')
                time.sleep(3)
        for key in jobs:
            job = json.loads(jobs[key])
            self.req_id(job)
            time.sleep(10)

