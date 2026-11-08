import os
import requests
import time
import logging
from base64 import b64encode
from functools import wraps
from traceback import format_exc
from utils.proxy_requests import proxies
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GEM PICDOWNLOAD')

class PicDownload:
    def __init__(self, url, collectionAddress):
        self.url = url
        self.headers = {
            "accept": "application/json",
            # "accept-encoding": "gzip,",
            "accept-language": "zh-CN,zh;q=0.9",
            # "content-type": "application/json",
            "dnt": "1",
            "origin": "https://www.gem.xyz",
            "referer": "https://www.gem.xyz/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.proxies = proxies
        self.rds = DataUtils('spider')
        self.address = collectionAddress
        self.table = 'gem_icon'

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
    def download(self):
        """
        pic download add proxy
        """
        r = requests.get(self.url,headers=self.headers,proxies=self.proxies)
        logger.info(f'picdownload status: {r.status_code}')
        if r.status_code != 200:
            logger.error('response status_code error')
            raise Exception(r.status_code)
        return r

    retry()
    def push(self, r):
        """
        upload pic to oss and get the new picurl
        """
        upload_url = 'http://' + os.getenv('GEM_ADMIN_HOST', '') + ':8534/file/uploadImageBase64'
        data = {
            'image':'data:image/jpeg;base64,'+b64encode(r.content).decode('utf-8')
        }
        res = requests.post(upload_url,json=data)
        push_result = res.json()
        if push_result['status'] == 0:
            if push_result['data']['status'] == 0:
                if push_result['data']['url']:
                    return push_result['data']['url']
                else:
                    raise Exception('url is None')
            else:
                raise Exception('the inner layer status code error')
        else:
            raise Exception('the outer layer status code error')

    def down_to_up(self):
        r = self.download()
        if r:
            url = self.push(r)
            # update the icon url into mysql gem table
            # update_sql = f'update {self.table} set icon={repr(url)} where collectionAddress={repr(self.address)};'
            # self.rds.update(update_sql)
            replace_into_sql = f"replace into {self.table}(address,icon) values({repr(self.address)},{repr(url)});"
            self.rds.insert(replace_into_sql)
            return url
        else:
            logger.error('pic download error pass')
            return None