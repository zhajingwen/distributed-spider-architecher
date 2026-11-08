import os
import json
import time
import logging
import datetime
import requests
from hashlib import md5
from functools import wraps
from traceback import format_exc
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies
from .alert import alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Opensea List')
env = os.environ.get('env')

class OpenseaList:
    """
    直接存储图片外链版本
    """
    def __init__(self):
        self.num = 0
        self.rds = DataUtils('spider')
        self.table = 'opensea'
        self.redis_cli = redis_cli()
        self.icon_jobs = 'opensea:icon:jobs_backup'
        self.detail_jobs = 'opensea:detail:jobs_backup'
        self.pending_jobs = 'opensea:pending:jobs_backup'
        self.list_done = 'opensea:list:done'
        self.alert_done = 'opensea:alert:done'
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
        self.url = 'https://api.pro.opensea.io/analytics/minting'

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 3
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
    def req(self, duration):
        """
        发起列表页请求
        """
        payloads = {
            "filters": {"price": {}, "holders": {}, "duration": "15_mins", "onlyMintable": False},
            "offset": 0,
            "limit": 50,
            "sort": {"mintCount": -1}
        }
        logger.info(f'{duration} {self.url}')
        res = requests.post(self.url, json=payloads, headers=self.headers, proxies=proxies)
        logger.info(f"{res.status_code} {duration} {self.url}")
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')

        self.parse(res, duration)

    def parse(self, response, duration):
        """
        解析列表页数据
        mintChangePercentage_24h 值只有在24h的情况下才刷新
        """
        try:
            data = response.json()
        except:
            raise Exception(f'响应体异常 {response.text}')
        all_insert_sql_base = "replace into {}(id,collectionAddress,duration,firstMintAt," \
                              "collectionName,top_wallets,mintCount,mintPrice," \
                              "floorPrice,uniqueMintersPercentage,uniqueMinters,totalMintCount," \
                              "update_time,icon,mintChangePercentage_24h) values{};"
        # 是否刷新mintChangePercentage_24h值
        if duration == '24_hours':
            all_update_sql_base = 'UPDATE opensea SET duration=%s,top_wallets=%s,' \
                           'mintCount=%s,mintPrice=%s,floorPrice=%s,uniqueMintersPercentage=%s,uniqueMinters=%s,' \
                           'totalMintCount=%s,update_time=now(),mintChangePercentage_24h=%s WHERE id=%s'
        else:
            all_update_sql_base = 'UPDATE opensea SET duration=%s,top_wallets=%s,' \
                           'mintCount=%s,mintPrice=%s,floorPrice=%s,uniqueMintersPercentage=%s,uniqueMinters=%s,' \
                           'totalMintCount=%s,update_time=now() WHERE id=%s'

        insert_data = []
        ids_insert = []

        update_data = []
        ids_update = []
        collectionAddresses = []
        for i in data['data']:
            collectionAddress = i['collectionAddress']
            collectionAddresses.append(collectionAddress)
            try:
                mint_date = i['firstMintAt']
                mint_date = datetime.datetime.fromtimestamp(mint_date).strftime('%Y-%m-%d %H:%M:%S')
            except:
                continue

            # 告警去重
            if not self.redis_cli.sismember(self.alert_done, collectionAddress):
                # 热门NFT告警
                status = alert(i, duration)
                # 成功告警后加入去重队列
                if status:
                    # 加入去重队列
                    self.redis_cli.sadd(self.alert_done, collectionAddress)
            # 可能存在没有collectionName的情况
            name = i.get('collectionName', '')
            top_wallets = i['prominentMintersCount']
            mintCount = i['mintCount']
            # 可能存在空值的情况
            if i.get('mintPrice'):
                mintPrice = int(i['mintPrice']) / 1000000000000000000
                mintPrice = str(mintPrice)
            else:
                mintPrice = ''
            if i.get('floorPrice'):
                floorPrice = int(float(i['floorPrice'])) / 1000000000000000000
                floorPrice = str(floorPrice)
            else:
                floorPrice = ''
            uniqueMintersPercentage = i.get('uniqueMintersPercentage')
            if uniqueMintersPercentage:
                uniqueMintersPercentage = uniqueMintersPercentage/100
            uniqueMinters = i.get('uniqueMinters', 'NULL')
            totalMintCount = i.get('totalMintCount')
            # 部分没有图片
            icon = i.get('collectionImageUrl')
            id = md5(f"{collectionAddress}{duration}".encode('utf8')).hexdigest()
            if env != 'prod':
                logger.info(f'{name} {id} {collectionAddress}')
            # 部分没有详情页
            collectionSlug = i.get('collectionSlug')
            if collectionSlug:
                detail_job = {
                    'address':collectionAddress,
                    'collectionSlug': collectionSlug,
                }
                # 将详情任务塞入redis
                self.redis_cli.sadd(self.detail_jobs, json.dumps(detail_job))
            if not icon:
                icon = 'null'
            else:
                icon = repr(icon.replace('w=500','w=50'))
            mintChangePercentage_24h = i.get('mintChangePercentage')
            # 首次采集
            if not self.redis_cli.sismember(self.list_done,id):
                if not totalMintCount:
                    totalMintCount = 'null'
                if not mintChangePercentage_24h:
                    mintChangePercentage_24h = 'null'
                if not uniqueMintersPercentage:
                    uniqueMintersPercentage = 'null'
                insert_sql = f"({repr(id)},'{collectionAddress}','{duration}',{repr(mint_date)},{repr(name)}," \
                             f"{top_wallets},{mintCount},'{mintPrice}','{floorPrice}',{uniqueMintersPercentage}," \
                             f"{uniqueMinters},{totalMintCount},{int(time.time())},{icon},{mintChangePercentage_24h})"
                insert_data.append(insert_sql)
                ids_insert.append(id)
            # 刷新数据
            else:
                if duration == '24_hours':
                    update_one_data = (
                        duration,
                        top_wallets,
                        mintCount,
                        mintPrice,
                        floorPrice,
                        uniqueMintersPercentage,
                        uniqueMinters,
                        totalMintCount,
                        mintChangePercentage_24h,
                        id
                    )
                else:
                    update_one_data = (
                        duration,
                        top_wallets,
                        mintCount,
                        mintPrice,
                        floorPrice,
                        uniqueMintersPercentage,
                        uniqueMinters,
                        totalMintCount,
                        id
                    )
                update_data.append(update_one_data)
                ids_update.append(id)
        if insert_data:
            # 多条记录一次性插入
            all_update_sql = all_insert_sql_base.format(self.table, ','.join(insert_data))
            status = self.rds.insert(all_update_sql)
            # 入库成功记录
            if status:
                for c in ids_insert:
                    self.redis_cli.sadd(self.list_done,c)
        if update_data:
            # 入库返回值
            status = self.rds.update_many(all_update_sql_base, update_data)
            # 入库成功记录
            if status:
                for c in ids_update:
                    self.redis_cli.sadd(self.list_done,c)
        # pending爬虫依赖该地址列表作为POST请求体
        pending_jobs = {"payload":collectionAddresses}
        self.redis_cli.sadd(self.pending_jobs,json.dumps(pending_jobs))

    def get_all_interal(self):
        """
        获取所有时间粒度的数据
        """
        durations = ['15_mins','30_mins','1_hour','24_hours']
        for d in durations:
            self.req(d)

    def run(self):
        """
        每天8-11点这个区间，每10分钟刷新一次
        """
        if env == 'prod':
            while True:
                # 18日切成早上刷新
                # today_now = datetime.datetime.now()
                # today_at_08 = today_now.replace(hour=8, minute=0, second=0)
                # today_at_11 = today_now.replace(hour=11, minute=0, second=0)
                #
                # if today_at_08 < today_now < today_at_11:
                #     self.get_all_interal()
                # else:
                #     logger.info('等待调度中...')
                self.get_all_interal()
                time.sleep(10 * 60)
        else:
            self.get_all_interal()

