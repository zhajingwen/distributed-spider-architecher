import json
# import requests
import time
import logging
from functools import wraps
from traceback import format_exc
from .free_mint.picdownload import PicDownload
from utils.rds import DataUtils
# from threading import Thread
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Free Mint Push All Data')

class Icon:
    def __init__(self):
        self.db = DataUtils('spider')
        self.redis_cli = redis_cli()
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

    @retry()
    def get_icon(self, oridata):
        """
        将没有下载过的icon下载并且上传到sso
        """
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
                        logger.info(f'icon 刷新成功：{icon}')

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
