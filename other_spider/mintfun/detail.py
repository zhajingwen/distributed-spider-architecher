import requests
import logging
import time
import re
import json
import random
import os
import datetime
import pytz
from traceback import print_exc
from functools import wraps
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MintFun Detail')
env = os.environ.get('env')

class Detail:
    def __init__(self):
        """
        获取域名解析地址
        """
        self.headers = {
            # "Accept": "*/*",
            # "Accept-Encoding": "gzip",
            # "Accept-Language": "zh-CN,zh;q=0.9",
            # "Content-Type": "application/json",
            # "Dnt": "1",
            # "Origin": "https://app.ens.domains",
            # "Referer": "https://app.ens.domains/",
            # "Sec-Ch-Ua": "\"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"114\", \"Google Chrome\";v=\"114\"",
            # "Sec-Ch-Ua-Mobile": "?0",
            # "Sec-Ch-Ua-Platform": "\"macOS\"",
            # "Sec-Fetch-Dest": "empty",
            # "Sec-Fetch-Mode": "cors",
            # "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        self.detail_jobs = 'mintfun:detailjobs'
        self.redis_cli = redis_cli()
        self.insert_done = 'mintfun:insertdone'
        self.rds = DataUtils()
        # self.url = 'https://ens.vision/api/tokens/search/v1'
        self.url_base = 'https://ens.vision/_next/data/{}/en/name/{}.json?handle={}'
        # 有些域名没有解析 404
        self.black_list = 'mintfun:blacklist'
        self.token_time = "mintfun:token"

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

    @retry(2)
    def req(self, job, token):
        """
        请求address信息并且入库
        """
        slug = job['slug']
        lastMinted = job['lastMinted']
        utc_time = datetime.datetime.strptime(lastMinted, "%Y-%m-%dT%H:%M:%SZ")
        china_tz = pytz.timezone('Asia/Shanghai')
        Last_active = utc_time.astimezone(china_tz).strftime("%Y-%m-%d %H:%M:%S")
        projects = job['collectionsMinted']
        streak = job['streak']
        points = job['totalPoints']
        points = int(points)
        # 未插入过
        if not self.redis_cli.sismember(self.insert_done, slug):
            if '.eth' in slug:
                head = slug.replace('.eth','')
                if self.redis_cli.sismember(self.black_list,head):
                    logger.info(f'该域名 {head} 无法解析，在黑名单中')
                    return
                url = self.url_base.format(token,head,head)
                logger.info(f'GET {url}')
                res = requests.get(url,headers=self.headers,proxies=proxies)
                logger.info(f'response {res.status_code} {url}')
                if res.status_code != 200:
                    if res.status_code == 404:
                        logger.info(f'response 404: {url}')
                        self.redis_cli.sadd(self.black_list,head)
                        return
                    else:
                        raise Exception(f'响应码异常：{res.status_code} {url}')
                address = res.json()["pageProps"]["loadedNameData"]["owner"]
            else:
                address = slug
            if address:
                sql = f'replace into mintfun values({repr(slug)},{repr(address)},{repr(Last_active)},{projects},{streak},{points},null,now());'
                status = self.rds.insert(sql)
                if status:
                    self.redis_cli.sadd(self.insert_done,slug)
                else:
                    logger.warning(f'insert失败：{sql}')
            else:
                logger.info(f'地址解析失败：{slug} ')
        # 插入过，需要更新
        else:
            select_sql = f'select points from mintfun where minter={repr(slug)};'
            old_points = self.rds.select(select_sql)[0]
            # logger.info(old_points)
            old_points = int(old_points['points'])
            points_24h = points - old_points
            sql = f'update mintfun set points_24h={points_24h} where minter={repr(slug)}'
            status = self.rds.insert(sql)
            if not status:
                logger.warning(f'update失败：{sql}')

    @retry()
    def get_token(self):
        """
        获取解析接口token
        """
        url = 'https://ens.vision/name/p0888'
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            # token定长21
            pattern = '\/_next\/static\/(.{10,30})\/_buildManifest'
            token = re.findall(pattern, res.text.strip(), re.S)[0]
            # 设置3小时过期时间
            self.redis_cli.setex(self.token_time,3*60*60,token)
            logger.info(f'token 刷新成功：{token}')
            return token
        else:
            logger.error(f'{res.status_code} {url}')
            return None

    def run(self):
        """
        启动入口 定时调度
        """
        while True:
            job = self.redis_cli.spop(self.detail_jobs)
            # 获取token 过期时间3小时
            token = self.redis_cli.get(self.token_time)
            if not token:
                token = self.get_token()
            if job:
                if not token:
                    logger.error(f'获取token失败！')
                    break
                job = json.loads(job)
                # 异步3并发
                t = Thread(target=self.req,args=(job,token,))
                t.start()
                time.sleep(0.3)
            else:
                logger.info('任务已消费完，等待...')
                time.sleep(10*60)
