import requests
import time
import json
import logging
from urllib.parse import urlencode,urlparse,unquote,urldefrag
from urllib.parse import parse_qs, urlparse
from lxml import etree
from hashlib import md5
from functools import wraps
from traceback import print_exc
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('EtherScan Spider')


class EtherScan:
    def __init__(self):
        self.params = {
            'q': 'gasguzzler',
            'draw': '2',
            'columns[0][data]': 'rank',
            'columns[0][searchable]': 'true',
            'columns[0][orderable]': 'false',
            'columns[0][search][regex]': 'false',
            'columns[1][data]': 'address',
            'columns[1][searchable]': 'true',
            'columns[1][orderable]': 'false',
            'columns[1][search][regex]': 'false',
            'columns[2][data]': 'txfee_3h',
            'columns[2][searchable]': 'true',
            'columns[2][orderable]': 'true',
            'columns[2][search][regex]': 'false',
            'columns[3][data]': 'gasused_3h',
            'columns[3][searchable]': 'true',
            'columns[3][orderable]': 'true',
            'columns[3][search][regex]': 'false',
            'columns[4][data]': 'txfee_24h',
            'columns[4][searchable]': 'true',
            'columns[4][orderable]': 'true',
            'columns[4][search][regex]': 'false',
            'columns[5][data]': 'gasused_24h',
            'columns[5][searchable]': 'true',
            'columns[5][orderable]': 'true',
            'columns[5][search][regex]': 'false',
            'columns[6][data]': 'analytics',
            'columns[6][searchable]': 'true',
            'columns[6][orderable]': 'false',
            'columns[6][search][regex]': 'false',
            'order[0][column]': '3',
            'order[0][dir]': 'desc',
            'start': '0',
            'length': '50',
            'search[regex]': 'false',
            '_': f'{int(time.time()*1000)}'
        }
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9",
            # "cookie": "<COOKIE_CRYPTO_SCAN>",
            "dnt": "1",
            "referer": "https://etherscan.io/gastracker",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest"
        }
        self.redis_cli = redis_cli()
        self.crypto_scan_job_key = 'crypto:scan:jobs_backup'

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

    @retry()
    def req(self):
        url_base = 'https://etherscan.io/datasourceHandler'
        params = urlencode(self.params)
        url = url_base + f'?{params}'
        res = requests.get(url,headers=self.headers,proxies=proxies)
        if res.status_code == 200:
            try:
                self.parse(res)
                logger.info('redis写入结束')
            except:
                print_exc()
        else:
            logger.warning(f'请求错误：{res.status_code}  {url} {res.text}')

    def parse(self,res):
        data = res.json()
        blockchain = 'ETH'
        for d in data['data']:
            tree = etree.HTML(d['address'])
            name = tree.xpath('//a/text()')[0]
            address = tree.xpath('//a/@href')[0].replace('/address/','')
            id = md5(f'{blockchain}{address}'.encode()).hexdigest()
            result = {
                'id': id,
                'blockchain':blockchain,
                'address':address,
                'name': name
            }
            self.redis_cli.sadd(self.crypto_scan_job_key,json.dumps(result))

    def run(self):
        # 15分钟跑一次
        while True:
            self.req()
            time.sleep(15*60)
