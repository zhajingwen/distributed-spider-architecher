import json
import logging
import time
import datetime
import hashlib
import requests
import os
from functools import wraps
from traceback import format_exc
from threading import Thread
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko')
env = os.environ.get('env')

class Spider:
    """
    symbol有可能完全一样，URL和ID代表唯一性
    """
    def __init__(self):
        # 校验数据，且，生成两个全局变量self.symbol_up_urls （jobs）  self.coins_symbol_json (coingecko list)
        self.build_relationship()
        logger.info(f'校验完成，开始采集（去重模式，ID+日期）')
        self.rds = DataUtils('spider')
        self.redis_cli = redis_cli()
        self.duplitude_key = 'coingecko'

    def build_relationship(self):
        """

        确认符合研究院给的数据是否能与coingecko对应上
        符合，确认，修正

        """
        path = 'other_spider/coingecko_once/Q3/'
        # 格式化官方币种清单为{"zyn":    {
        #         "id": "zynergy",
        #         "symbol": "zyn",
        #         "name": "Zynergy"
        #     }}这种格式
        with open(f'{path}allcoins_ck') as f:
            coins = f.read().strip()
            coins_list = json.loads(coins)
        # CK币种清单  创建以symbol为KEY的coingecko清单
        coins_symbol_json = {}
        coins_id_json = {}
        for item in coins_list:
            coins_symbol_json[item['symbol']] = item
            coins_id_json[item['id']] = item
        # 建立symbol URL ID map 关系
        # symbol url map
        self.url_symbol = {}
        # url url切片ID对应关系
        self.url_urlid = {}
        with open(f'{path}jobs')as f:
            content = f.read().strip().split('\n')
            for row in content:
                symbol_url = row.strip()
                # print(symbol_url)
                if symbol_url:
                    symbol_url = symbol_url.split('	')
                    symbol = symbol_url[0].strip()
                    url = symbol_url[1].strip()
                    # URL校验
                    if 'https' in url:
                        # 核对syboml有效性 一般存在由于笔误导致的无效，需要责任人确认更正
                        symbol_low = symbol.lower()
                        # 从URL中抽取出ID
                        id_ = url.split('/')
                        if id_[-1]:
                            id = id_[-1]
                        else:
                            id = id_[-2]
                        if symbol_low not in coins_symbol_json:
                            logger.error(f'无该币：{symbol} {url}')
                        else:
                            self.url_symbol[url] = symbol
                            self.url_urlid[url] = id
                    # URL提取失败提醒
                    else:
                        logger.info(f'URL异常：{url}')
        # 定义为全局变量
        self.coins_id_json = coins_id_json
        self.coins_symbol_json = coins_symbol_json

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
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning(f'重试超过次数{args} {kwargs}')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry(3)
    def get_one_day(self, param, id, datadate, datatimestamp, symbol, url_coin):
        """
        请求数据
        param： 日期："05-04-2023"
        id：  coingecko币对应的站内ID
        datadate：币当天日期形式2023-06-27 16:32:12
        datatimestamp 币当天的 时间戳1687854732
        """
        # 请求去重
        content = f'{id}{param}'
        res_md5 = hashlib.md5(content.encode('utf8')).hexdigest()
        status = self.redis_cli.sismember(self.duplitude_key,res_md5)
        if status:
            logger.info(f'已采集 去重！：{content}')
            return
        headers = {
            "accept": "application/json"
        }
        # url = "https://api.coingecko.com/api/v3/coins/velo/history"
        url = f"https://api.coingecko.com/api/v3/coins/{id}/history"
        params = {
            # "05-04-2023"
            "date": param
        }
        logger.info(f'get: {url}  {params}')
        if env == 'local':
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.get(url, headers=headers, params=params, proxies=proxies)
        logger.info(f'{id} {param} {response.status_code}')
        try:
            volume = response.json()['market_data']['total_volume']['usd']
        except:
            if 'symbol' in response.json():
                # 同样去重，否则补数据会重跑，浪费资源
                logger.info(f'该日期无数据：{content}')
                self.redis_cli.sadd(self.duplitude_key, res_md5)
            else:
                logger.error(f"未知错误：{response.json()} {id}")
            return
        volume = int(volume)
        spider_time = int(time.time())
        # url_coin = self.symbol_up_urls[symbol]
        sql = f"replace into coingecko2 values ({repr(res_md5)},{repr(id)},{repr(symbol)}," \
              f"{volume},{repr(datadate)},{datatimestamp},{spider_time},{repr(url_coin)});"
        self.rds.insert(sql)
        self.redis_cli.sadd(self.duplitude_key,res_md5)
        logger.info(f'成功入库：{content}')

    def one_date(self, param, datadate, datatimestamp):
        """
        单个日期的，所有币种
        10并发/s  且每天的数据所有币种跑完再跑第二天的
        """
        for url in self.url_symbol:
            symbol_up = self.url_symbol[url]
            # url切片末尾，切出的ID
            url_id = self.url_urlid[url]
            # 如果能通过URL切片中的ID直接关联匹配到API ID，那么就采用该ID
            if url_id in self.coins_id_json:
                id = url_id
            # 如果不行，就通过symbol去匹配
            else:
                # 瑞波币
                if url_id == 'xrp':
                    id = 'ripple'
                else:
                    # coingecko接口对应的币的ID
                    id = self.coins_symbol_json[symbol_up.lower()]['id']

            # 开发环境
            if env == 'local':
                self.get_one_day(param, id, datadate, datatimestamp,symbol_up, url)
                time.sleep(10)
            else:
                t = Thread(target=self.get_one_day,args=(param, id, datadate, datatimestamp,symbol_up,url,))
                t.start()
                # 并发限制为10/s
                time.sleep(0.1)

    def run(self, start, end):
        """
        入口
        """
        while True:
            start_date = start.strftime('%Y-%m-%d %H:%M:%S')
            param = start.strftime('%d-%m-%Y')
            datatimestamp = int(start.timestamp())
            # 执行
            self.one_date(param,start_date,datatimestamp)
            start += datetime.timedelta(days=1)
            if start > end:
                break

