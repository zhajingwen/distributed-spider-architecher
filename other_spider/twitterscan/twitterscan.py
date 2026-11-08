import requests
import schedule
import time
import os
import logging
from hashlib import md5
from datetime import datetime,date, timedelta
from utils.proxy_requests import proxies
from utils.rds import DataUtils
from traceback import format_exc
from functools import wraps
from math import ceil
from threading import Thread
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TwitterScan Spider')
env = os.environ.get('env')

class Spider:
    def __init__(self):
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9",
            "dnt": "1",
            "sec-ch-ua": "\"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"108\", \"Google Chrome\";v=\"108\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        self.rds = DataUtils('spider')
        self.table_trending = 'twitterscan_trendingtokens'
        self.table_kol = 'twitterscan_kol'
        self.super_kol_tokens = []
        self.super_kol_data = []
        self.builder_tokens = []
        self.builder_data = []
        self.vc_tokens = []
        self.vc_data = []

    def retry(*args):
        """
        定义重试装饰器
        """
        # 重试次数如果不自定义那就是默认的 10次
        if args:
            num = args[0]
        else:
            num = 10
        def recieve_func(func):
            @wraps(func)
            def wrapper(*args,**kwargs):
                retry_num = 0
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试{retry_num}...')
                        if 'Proxy Error' in format_exc():
                            logger.warning('Proxy Err')
                        elif 'ProxyError' in format_exc():
                            logger.warning('Proxy Err')
                        elif 'SSLEOFError' in format_exc():
                            logger.warning('SSLEOFErr')
                        elif 'timed out' in format_exc():
                            logger.warning('timed out')
                        elif '451 Client Error:' in format_exc():
                            logger.warning('451 Client Err')
                        elif 'RetryError' in format_exc():
                            logger.warning('RetryErr')
                        else:
                            logger.info(format_exc())
                        retry_num += 1
                        if retry_num > num:
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(5)
                return res
            return wrapper
        return recieve_func

    @retry()
    def req_trending(self, spider_date, spider_time, yesterday):
        """
        发起trending tokens 请求
        列表清单只有7条数据，感觉这网站几乎倒闭
        """
        url = 'https://api.twitterscan.com/appapi/twitter-scan/trading-token-v2?page_size=20&page_num=1'
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'trending {res.status_code} {url}')
        try:
            self.parse_trending(res, spider_date, spider_time, yesterday)
        except:
            logger.error(format_exc())
            logger.error('trending解析异常')

    def parse_trending(self, response, spider_date, spider_time, yesterday):
        """
        解析trending tokens
        """
        data = response.json()['data']['records']
        all_update_sql_base = "replace into {}(id,coin_name,change_percent_24h," \
                              "scores,scores_change_percent,spider_time,spider_date,price,7d,volume_24h) values{};"
        sql_values = []
        for d in data:
            price = d['price']
            change_percent_7d = d['change_percent_7d']
            change_percent_7d = f'{change_percent_7d}%'
            # 24HVolume
            total_volume = d['total_volume']
            # tokenname str
            coin_name = d['coin_name']
            # 24小时变化的幅度 str
            change_percent_24h = d['change_percent_24h']
            change_percent_24h =f'{change_percent_24h}%'
            # hot scores int
            mention_7d = d['mention_7d']
            select_sql = f'select scores from {self.table_trending} where ' \
                         f'coin_name={repr(coin_name)} and spider_date={repr(yesterday)};'
            # 如果查不到会返回 ()
            # 如果有值 [{'scores': 1140}]
            old_scores = self.rds.select(select_sql)
            if old_scores:
                old_scores = old_scores[0]['scores']
            else:
                old_scores = 0
            if old_scores == 0:
                scores_change_percent = '昨日无分'
            else:
                scores_change_percent = round(((mention_7d-old_scores)/old_scores)*100,2)
                scores_change_percent = f'{scores_change_percent}%'
            id = md5(f'{coin_name}{spider_time}{d}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(coin_name)},{repr(change_percent_24h)},{mention_7d}," \
                         f"{repr(scores_change_percent)},{spider_time},{repr(spider_date)}," \
                         f"{price},{repr(change_percent_7d)},{total_volume})"
            sql_values.append(update_sql)
            if data.index(d) == 19:
                break
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(self.table_trending, ','.join(sql_values))
            self.rds.insert(all_update_sql)

    @retry()
    def req_kol(self, spider_date, spider_time):
        """
        请求 crpto kol
        统计 tokens计数
        结构化数据：写入数据库
        """
        # base_url = 'https://api.twitterscan.com/appapi/twitter-scan/trading-kol-v2?category={}&page_num={}&page_size=20'
        base_url = 'https://api.twitterscan.com/appapi/twitter-scan/trading-kol-v3?category={}&page_num={}&page_size=20'
        categorys = ['superkol','builder','vc']
        jobs = []
        # 遍历所有标签
        for c in categorys:
            url = base_url.format(c,1)
            res = requests.get(url,headers=self.headers,proxies=proxies)
            logger.info(f'kol {res.status_code} {url}')
            if res.json()['msg'] == 'success':
                if res.status_code == 200:
                    pages = res.json()['data']['count']
                    pages = ceil(pages/20)
                    # 遍历所有翻页
                    for p in range(2,pages+1):
                        # 接口最多支持返回30页
                        if p > 30:
                            logger.warning(f'{c} 翻页结束')
                            break
                        t = Thread(target=self.req_kol_child,args=(p,c,base_url,))
                        t.start()
                        jobs.append(t)
                    try:
                        # 解析页面
                        self.parse_kol(res, c)
                    except:
                        logger.error(format_exc())
                        logger.error(f'kol 解析异常 {url}')
                else:
                    logger.error(f'kol {c}请求异常')
            else:
                logger.error(f'kol {c}请求异常')
        # 等待所有线程运行结束
        logger.info('等待所有线程运行结束...')
        for t in jobs:
            t.join()
        logger.info('所有爬虫工作完毕')
        # 请求或者解析出现异常
        if not self.super_kol_tokens:
            logger.error('程序崩溃')
            return
        # 字典结构的统计计数
        super_kol_tokens_counter = dict(Counter(self.super_kol_tokens))
        builder_tokens_counter = dict(Counter(self.builder_tokens))
        vc_tokens_counter = dict(Counter(self.vc_tokens))
        all_update_sql_base = "replace into {}(id,username,coin_name," \
                              "token_count,tag,spider_time,spider_date) values{};"
        # logger.info(f'vc datas: {len(self.vc_data)} {len(set(self.vc_data))}')
        # logger.info(f'builder datas: {len(self.builder_data)} {len(set(self.builder_data))}')
        # logger.info(f'superkol datas: {len(self.super_kol_data)} {len(set(self.super_kol_data))}')
        # superkol builder vc 统一入库
        sql_values = []
        datas = [self.super_kol_data,self.builder_data,self.vc_data]
        for data in datas:
            for target_d in data:
                username = target_d['username']
                coin_name = target_d['coin_name']
                if datas.index(data) == 0:
                    tag = 'superkol'
                    token_count = super_kol_tokens_counter[coin_name]
                elif datas.index(data) == 1:
                    tag = 'builder'
                    token_count = builder_tokens_counter[coin_name]
                else:
                    tag = 'vc'
                    token_count = vc_tokens_counter[coin_name]
                id = md5(f'{target_d}{spider_time}'.encode('utf-8')).hexdigest()
                update_sql = f"({repr(id)},{repr(username)},{repr(coin_name)},{token_count}," \
                             f"{repr(tag)},{spider_time},{repr(spider_date)})"
                sql_values.append(update_sql)
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(self.table_kol, ','.join(sql_values))
            self.rds.insert(all_update_sql)

    @retry()
    def req_kol_child(self, page_num, c, base_url):
        """
        kol三个标签的翻页请求
        多线程异步
        """
        url = base_url.format(c, page_num)
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'kol {res.status_code} {url}')
        if res.json()['msg'] == 'success':
            if res.status_code == 200:
                try:
                    # 解析页面
                    self.parse_kol(res, c)
                except:
                    logger.error(format_exc())
                    logger.error(f'kol 解析异常 {url}')
            else:
                logger.error(f'kol {c}请求异常')
        else:
            logger.error(f'kol {c}请求异常')

    def parse_kol(self, res, c):
        """
        解析数据
        """
        data = res.json()['data'].get('records')
        if not data:
            logger.info(f'数据体为空 {res.json()}')
            return
        for r in data:
            username = r['username']
            top_token_list = r['top_token_list']
            for coin in top_token_list:
                coin_name = coin['coin_name']
                target_data = {
                    'username':username,
                    'coin_name':coin_name
                }
                logger.info(c,coin)
                if c == 'superkol':
                    self.super_kol_tokens.append(coin_name)
                    self.super_kol_data.append(target_data)
                elif c == 'builder':
                    self.builder_tokens.append(coin_name)
                    self.builder_data.append(target_data)
                else:
                    self.vc_tokens.append(coin_name)
                    self.vc_data.append(target_data)

    def all_api(self):
        """
        采集所有目标数据
        """
        spider_time = int(time.time())
        spider_date = datetime.now().strftime("%Y-%m-%d")
        yesterday = (date.today() + timedelta(days=-1)).strftime("%Y-%m-%d")
        self.req_trending(spider_date, spider_time, yesterday)
        # self.req_kol(spider_date, spider_time)

        # reset global variable every time
        self.reset_global_variable()

    def reset_global_variable(self):
        """
        reset the global variable
        otherwise the statitical data must be wrong,it is accumulated every day
        """
        self.super_kol_tokens = []
        self.super_kol_data = []
        self.builder_tokens = []
        self.builder_data = []
        self.vc_tokens = []
        self.vc_data = []

    def run(self):
        """
        启动入口 定时调度
        """
        logger.info('任务启动...')
        if env == 'prod':
            # 每天7：00 启动
            schedule.every().day.at("07:00").do(self.all_api)
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            self.all_api()

    def create(self):
        self.rds.create_table()

    def rerun(self):
        spider_time = int(time.time())
        spider_date = datetime.now().strftime("%Y-%m-%d")
        yesterday = (date.today() + timedelta(days=-1)).strftime("%Y-%m-%d")
        self.req_trending(spider_date, spider_time, yesterday)
        self.reset_global_variable()
