import os
import json

import requests
import time
import logging
from functools import wraps
from traceback import format_exc
from .picdownload import PicDownload
from utils.rds import DataUtils
from threading import Thread
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Free Mint Push All Data')

class PushAllData:
    def __init__(self):
        self.url = 'http://' + os.getenv('GEM_ADMIN_HOST', '') + ':8534/admin/pushPoolData'
        self.table = 'gem'
        self.db = DataUtils('spider')
        self.redis_cli = redis_cli()
        self.freemint_jobs_key = 'gem:freemint:jobs_backup'
        self.icon_table = 'gem_icon'

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
                        logger.info(format_exc())
                        retry_num += 1
                        if retry_num > num:
                            logger.error('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(20)
                return res
            return wrapper
        return recive_func

    retry()
    def push(self, oridata):
        """
        push compelet data
        """
        # all tokens batch push
        datas = []
        for i in oridata['data']:
            contract = i['collectionAddress']
            collection_name = i.get('collectionName', '')
            collectionImageUrl = i.get('collectionImageUrl','')
            if collectionImageUrl:
                icon_select_sql = f'SELECT icon FROM `{self.icon_table}` WHERE address="{contract}"'
                try:
                    icon = self.db.select(icon_select_sql)
                except:
                    icon = ''
                if icon:
                    icon = icon[0]['icon']
                # mysql gem table have not the key or the key value is null
                if not icon:
                    icon = PicDownload(collectionImageUrl,contract).down_to_up()
                    # still exist None
                    if not icon:
                        icon = ''
            else:
                icon = ''
            select_sql = f'SELECT externalUrl FROM `gem` WHERE collectionAddress="{contract}"'
            logger.info(select_sql)
            try:
                externalUrl = self.db.select(select_sql)
            except:
                externalUrl = ''
            # no select result
            if externalUrl == ():
                externalUrl = ''
            if externalUrl:
                externalUrl = externalUrl[0]['externalUrl']
                # result is null
                if not externalUrl:
                    externalUrl = ''
            link = externalUrl
            mint_count_24 = i['mintCount']
            mint_count_change_24 = i.get('uniqueMintersPercentage', '')
            # 可能存在空值的情况
            if i.get('mintPrice'):
                mintPrice = int(i['mintPrice']) / 1000000000000000000
                mintPrice = str(mintPrice)
            else:
                mintPrice = ''
            mint_price = mintPrice
            if i.get('floorPrice'):
                floorPrice = int(i['floorPrice']) / 1000000000000000000
                floorPrice = str(floorPrice)
            else:
                floorPrice = ''
            floor_price = floorPrice
            # mint_total
            mint_total = i.get('totalMintCount', '')
            mint_supply = i.get('totalSupply','')
            # wait for confirm
            address_total = i.get('uniqueHolders','')
            single_data = {
                "contract": contract,
                "collection_name": collection_name,
                "icon": icon,
                "link": link,
                "mint_count_24": mint_count_24,
                "mint_count_change_24": mint_count_change_24,
                "mint_price": mint_price,
                "floor_price": floor_price,
                "mint_total": mint_total,
                "mint_supply": mint_supply,
                "address_total": address_total
            }
            datas.append(single_data)
        data = {
            "list": datas
        }
        res = requests.post(self.url,json=data)
        push_status = res.json()
        if push_status['status'] != 0:
            logger.error(data)
            raise Exception(str(push_status))
        else:
            logger.info('push success')


    def consumer_redis(self):
        while True:
            try:
                data = self.redis_cli.spop(self.freemint_jobs_key)
            # redis connection maybe lost broken
            except:
                self.redis_cli = redis_cli()
                continue
            if data:
                data = json.loads(data)
                self.push(data)
            else:
                logger.info('wait for new coinsadjust in')
                time.sleep(3)
