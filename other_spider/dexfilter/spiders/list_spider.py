import time
import requests
import logging
import json
from copy import deepcopy
from urllib.parse import urlencode
from traceback import format_exc
from .data_filter import Filter
from .retry import retry,retry_net
from threading import Thread
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('LIST SPIDER')

class List:
    """
    nt == 0 小市值
    nt == 1 早期造富
    """
    def __init__(self):
        self.headers = {
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
            'accept': 'application/json, text/plain, */*',
            'dnt': '1',
            'sec-ch-ua-mobile': '?0',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko)',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://dexfilter.com/',
            'accept-encoding': 'gzip',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7'
        }
        self.filter = Filter()
        self.redis_cli = redis_cli()
        self.redis_key = 'dexfilter:list:data'
        # self.redis_workdone_key = 'dexfilter:list:done'
        # self.thread_list = []
        # self.redi_cookie_key = 'dexfilter:cookie'
        self.cookies_store = 'dexfilter:cookies'

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hood
        """
        while True:
            cookie_json = self.redis_cli.spop(self.cookies_store)
            if not cookie_json:
                logger.warning('当前没有可调用的cookies,等待...')
                time.sleep(5)
                continue
            cookie_dict = json.loads(cookie_json)
            # cookie超过有效期，那么久重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30*60:
                logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry()
    def req(self, chain, params, page=1):
        """
        请求页的入口，如果没有可调用的cookies，应该hood
        发起列表页请求
        已确认该请求重试策略，重试会剔除无效的cookies，获取新的cookies，那么就很好的平衡了dexfilter间歇性上线cloudflare的问题
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        # url = f'https://dexfilter.com/v1/{chain}/index?{urlencode(params)}&page={page}'
        url = f'https://dexfilter.com/v1/{chain}/indexV1?{urlencode(params)}&page={page}'
        logger.info(f'pagenum: {page} request: {url}')
        # {"id": "718fd558da3df70d254df15dc52944f8", "proxy": "<PROXY_URL>", "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36", "cf": "<CF_CLEARANCE>", "timestamp": 1671091997}
        # 以下三项均来自rpc
        self.headers['user-agent'] = cookie_dict['ua']
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        res = retry_net(cookie_dict, url, self.headers, proxies)
        if not res:
            return
        # 503 forbidden
        logger.info(f'response code: {res.status_code} {url}')
        # 当响应码异常的时抛出异常让重试装饰器重试
        if (res.status_code == 504) or (res.status_code == 502):
            logger.warning(f'Gateway time-out 重试：pagenum: {page} {url}')
            raise Exception('504 or 502')
        if res.status_code == 503:
            logger.info(f'当前cookies被封了{cookie_dict} 准备重试...')
            raise Exception('503')
        if res.status_code == 500:
            logger.info(f'{cookie_dict} 500 err 准备重试...')
            raise Exception('500')
        if res.status_code == 403:
            logger.info(f'{cookie_dict} 403 err 准备重试...')
            raise Exception('403')
        self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        try:
            # {"status":true,"code":200,"msg":"success","data":[]}
            if not res.json()['data']:
                logger.info(f'该条件{params}列表页无法获取数据：{res.json()}')
                return
            self.parse(res.json(), chain, params)
            pageCount = res.json()['data']['pageCount']
            if page == 1:
                logger.info(f'一共{pageCount}页')
        except:
            logger.info(format_exc())
            logger.error(f'params: {params} resposne: {res.text}')
            return
        # 通过page 控制避免递归（非递归执行方式）
        if page == 1:
            # 不止1页才翻页
            if pageCount > 1:
                for i in range(2,pageCount+1):
                    t = Thread(target=self.req,args=(chain, params, i))
                    t.start()

    def parse(self,data, chain, params):
        """
        解析列表页
        """
        # {"status": true, "code": 200, "msg": "success", "data": []}
        status = data['status']
        code = data['code']
         # = 0
        nt = params['nt']
        # 小市值
        if nt == 0:
            func = self.filter.filter_list_data_marketcap
        # 早期造富
        else:
            func = self.filter.filter_list_data_early
        if status:
            if code == 200:
                if data['data']:
                    list_data = data['data']['list']
                    logger.info(f'原始数据长度：{len(list_data)}')
                    filtered_data = func(list_data)
                    logger.info(f'过滤后的数据长度：{len(filtered_data)}')
                    # logger.info(filtered_data)
                    with self.redis_cli.pipeline(transaction=False)as pipe:
                        for data in filtered_data:
                            data['chain'] = chain
                            pipe.sadd(self.redis_key,json.dumps(data))
                        pipe.execute()
                else:
                    logger.warning(f'当前无数据：{data}')
            else:
                logger.error(data)
        else:
            logger.error(data)
                # return pageCount

    def all_chains_early(self, params, chains):
        """
        早期造富的条件
        采集所有公链
        """
        params['nt'] = 1
        params['date'] = "24h"
        for chain in chains:
            self.req(chain, params)

    def all_chains_small_marketcap(self, params, chains):
        """
        小市值
        """
        params['nt'] = 0
        params['date'] = "1h"
        for chain in chains:
            self.req(chain, params)

    def two_project(self):
        params = {
            "pool_column": "ub",
            "range_date": "5m",
            "rise_or_fall": "up",
            # "page": 1,
            "page_size": 100
        }
        chains = ['eth','bsc','pol','avax','arb','opt']
        # 可变变量在遇到修改的时候可能会错乱，故这里用深拷贝
        new_params = deepcopy(params)
        self.all_chains_early(params, chains)
        self.all_chains_small_marketcap(new_params, chains)

    def run(self):
        """
        定时执行，每1小时跑一次
        """
        while True:
            self.two_project()
            logger.info('当前批次列表页执行完毕')
            time.sleep(60*60*1)