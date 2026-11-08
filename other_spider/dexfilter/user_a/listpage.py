import time
import requests
import logging
import json
import re
from copy import deepcopy
from urllib.parse import urlencode
from traceback import format_exc
# from .data_filter import Filter
from other_spider.dexfilter.spiders.retry import retry,retry_net
from threading import Thread
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('USER_A SPIDER')

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
        # self.filter = Filter()
        self.redis_cli = redis_cli()
        # self.redis_key = 'dexfilter:list:data'
        # self.redis_workdone_key = 'dexfilter:list:done'
        # self.thread_list = []
        # self.redi_cookie_key = 'dexfilter:cookie'
        self.cookies_store = 'dexfilter:cookies'
        self.num_ids = {
            'eth':1,
            'bsc': 56,
            'pol': 137,
            'avax': 43114,
            'arb': 42161,
            'opt': 10,
            'cro':25,
        }

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
    def req(self, url, cookie_dict):
        logger.info(f'request: {url}')
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
        logger.info(f'response code: {res.status_code} {url}')
        # 当响应码异常的时抛出异常让重试装饰器重试
        if (res.status_code == 504) or (res.status_code == 502):
            logger.warning(f'Gateway time-out 重试：{url}')
            raise Exception('504 or 502')
        if res.status_code == '503':
            logger.info(f'当前cookies被封了{cookie_dict} 准备重试...')
            raise Exception('503')
        if res.status_code != 200:
            return
        else:
            # 真能获取到数据再把cookie放回去
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def req_list(self, chain, params, page=1):
        """
        请求页的入口，如果没有可调用的cookies，应该hood
        发起列表页请求
        已确认该请求重试策略，重试会剔除无效的cookies，获取新的cookies，那么就很好的平衡了dexfilter间歇性上线cloudflare的问题
        """
        # 获取cookie
        url = f'https://dexfilter.com/v1/{chain}/index?{urlencode(params)}&page={page}'
        cookie_dict = self.get_cookie()
        res = self.req(url, cookie_dict)
        if not res:
            logger.error(f'can not get data normally {url}')
            return
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
                    self.req_list(chain, params, i)

    def parse(self, data, chain, params):
        """
        解析列表页
        """
        # {"status": true, "code": 200, "msg": "success", "data": []}
        status = data['status']
        code = data['code']
        if status:
            if code == 200:
                if data['data']:
                    list_data = data['data']['list']
                    logger.info(f'原始数据长度：{len(list_data)}')
                    for coin in list_data:
                        coin['chain'] = chain
                        t = Thread(target=self.req_detail, args=(coin,))
                        t.start()
                    # filtered_data = func(list_data)
                    # logger.info(f'过滤后的数据长度：{len(filtered_data)}')
                    # logger.info(filtered_data)
                    # with self.redis_cli.pipeline(transaction=False)as pipe:
                    #     for data in filtered_data:
                    #         data['chain'] = chain
                    #         pipe.sadd(self.redis_key,json.dumps(data))
                    #     pipe.execute()
                else:
                    logger.warning(f'当前无数据：{data}')
            else:
                logger.error(data)
        else:
            logger.error(data)
                # return pageCount
    def req_detail(self, ori_data):
        """
        判断是否存在合约漏洞
        早期造富（3）和小市值（3）的规则不同，注意区分
        """
        id = re.sub('^d', '', ori_data['tbname'])
        ori_data['id'] = id
        # chains = ['eth','bsc','pol','avax','arb','opt']

        chain = ori_data['chain']
        num_id = self.num_ids[chain]
        token = ori_data['token']
        url = f'https://api.gopluslabs.io/api/v1/token_security/{num_id}?contract_addresses={token}'
        result = self.req(url)
        if not result:
            logger.error(f'响应体为空: {url}')
            return
        result = result.json()
        if result['result'] == {}:
            logger.info(f'貔貅该token响应体为空 {ori_data}')
            return
        # 注意token要转化成小写
        data = result['result'][token.lower()]
        # 貔貅  可能存在没有这个key的情况，但是好像也是否，参考 https://dexfilter.com/BSC/0x9F0DecF097839b82c7b4A1E8F2e408D94D065b3D
        # 通过下面的接口可以拿到精确的数值，但是没必要
        # https://aywt3wreda.execute-api.eu-west-1.amazonaws.com/default/IsHoneypot?chain=bsc2&token=0x97220571E7d009e2e865AD5777Fcd86A6B9a0950
        is_honeypot = data.get('is_honeypot',"0")
        # 能否收回所有权（否）；
        can_take_back_ownership = data.get('can_take_back_ownership',"0")
        # 买卖税率 str类型  "0"  "0.049999"
        if 'buy_tax' not in data:
            logger.info(f'貔貅该token没有买入税率 {ori_data}')
            return
        if 'sell_tax' not in data:
            logger.info(f'貔貅该token没有卖出税率 {ori_data}')
            return
        buy_tax = data['buy_tax']
        sell_tax = data['sell_tax']
        if (is_honeypot == "0") and (can_take_back_ownership == "0"):
            if (float(buy_tax) < 0.048) and (float(sell_tax) < 0.048):
                # 总市值:供应量*价格
                total_value = float(data['total_supply'])*ori_data['up']
                total_value = round(total_value, 2)
                # 总市值小于1000万
                if total_value < 10000000:
                    ori_data['total_value'] = total_value
                    self.redis_cli.sadd('dexfilter:result',json.dumps(ori_data))
                # format_content = gen_msg(ori_data)
                # sender(format_content,self.lark_bot_url,'dexfilter')
            else:
                logger.info(f'{token}买卖税率过大')
        else:
            logger.info(f'{token}不满足貔貅或者收回所有权')



    def allchains(self):
        """
        In order to prevent variable variables from passing data confusion; so ,the page param not put it in the dict
        """
        params = {
            "pool_column": "ub",
            "nt": "0",
            "range_date": "5m",
            "date": "24h",
            "pool_range": "20000_max",
            "rise_or_fall": "up",
            # "page": "1",
            "page_size": 100
        }
        chains = ['eth', 'bsc', 'pol', 'avax', 'fan', 'cro', 'aur', 'mri', 'mbe', 'arb', 'opt', 'dog', 'gno', 'cel', 'met', 'hec', 'ast', 'can']
        for chain in chains:
            if chain in self.num_ids:
                self.req(chain, params)
        # self.all_chains_early(params, chains)
        # 可变变量在遇到修改的时候可能会错乱，故这里用深拷贝
        # new_params = deepcopy(params)
        # self.all_chains_small_marketcap(new_params, chains)


    def run(self):
        """
        定时执行，每1小时跑一次
        """
        while True:
            self.allchains()
            logger.info('当前批次列表页执行完毕')
            time.sleep(60*60*1)

