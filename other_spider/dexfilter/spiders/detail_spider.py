import os
import json
import re
import logging
import time
import requests
from utils.redisdb import redis_cli
from .retry import retry,retry_net
from other_spider.cmc.bot.lark_bot import sender
from other_spider.dexfilter.alert.dict_to_content import gen_msg
from traceback import format_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DETAIL SPIDER')

class Detail:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.redis_list_key = 'dexfilter:list:data'
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7',
            'cache-control': 'no-cache',
            'dnt': '1',
            'pragma': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        self.result = []
        self.cookies_store = 'dexfilter:cookies'
        self.lark_bot_url = os.getenv('LARK_WEBHOOK_MONGREL_DOG', '')

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
    def req(self, url):
        """
        发起请求
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        # 以下三项均来自rpc
        self.headers['user-agent'] = cookie_dict['ua']
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        logger.info(f'start request: {url}')
        res = retry_net(cookie_dict, url, self.headers, proxies)
        if not res:
            return
        status = res.status_code
        # 当响应码异常的时抛出异常让重试装饰器重试
        if status in [403,500,502,503,504]:
            logger.info(f'{cookie_dict} {status} err 准备重试...')
            raise Exception(f'{status}')
        if status != 200:
            return
        logger.info(f'code: {status} {url}')
        result = res.json()
        # 如果能够拿到响应，那么就确认该cookies是有效的，就重新放回池子
        if result:
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return result

    def req_total_value(self, ori_data):
        """
        总市值：算出来的，发行量*当前市场价
        并且给ori_data新增两个字段，总市值和总持有人
        小市值项目需要该参数
        """
        id = re.sub('^d', '', ori_data['tbname'])
        chain = ori_data['chain']
        # url = f'https://dexfilter.com/{chain}/getRightInfo?tag={id}'
        url = f'https://dexfilter.com/v1/{chain}/getRightInfo?tag={id}'
        result = self.req(url)
        if not result:
            logger.warning(f'响应体为空: {url}')
            return
        if not result.get('data'):
            logger.warning(f'响应体异常: {url}')
            return
        # 发行量,部分发行量，数据格式不标准  代币供应量
        # 发行量：2320000000.000000000000000000，price：6.560754863045031e-05
        supply = result['data']['supply']
        if type(supply) == str:
            supply = int(supply.split('.')[0])
        else:
            supply = int(supply)
        # 当前市场价
        price = result['data']['up']
        logger.info(f'发行量：{supply}，price：{price}')
        if supply > 1e12:
            logger.info(f'代币供应超过一万e {url}')
            return
        # 总市值
        total_value = round(supply*price,2)
        # 总市值小于500万
        # 这里设置的阈值过小，几乎没有数据能过这道过滤
        if total_value < 5000000:
            ori_data['total_value'] = total_value
            # 持有人
            holders = result['data'].get('holders',0)
            if holders > 1000:
                ori_data['holders'] = holders
                ori_data['id'] = id
                self.check_flaw(ori_data)
                # return ori_data
            else:
                logger.warning(f'持有人小于1000：{url}')
        else:
            logger.warning(f'总市值超过500万：{url}')

    def check_flaw(self,ori_data):
        """
        判断是否存在合约漏洞
        早期造富（3）和小市值（3）的规则不同，注意区分
        """
        id = re.sub('^d', '', ori_data['tbname'])
        ori_data['id'] = id
        # chains = ['eth','bsc','pol','avax','arb','opt']
        num_ids = {
            'eth':1,
            'bsc': 56,
            'pol': 137,
            'avax': 43114,
            'arb': 42161,
            'opt': 10,

        }
        chain = ori_data['chain']
        num_id = num_ids[chain]
        token = ori_data['token']
        url = f'https://api.gopluslabs.io/api/v1/token_security/{num_id}?contract_addresses={token}'
        result = self.req(url)
        if not result:
            logger.warning(f'响应体为空: {url}')
            return
        if not result['result']:
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
        if 'total_supply' not in data:
            logger.info(f'total_supply None {ori_data}')
            return
        buy_tax = data.get('buy_tax',None)
        sell_tax = data.get('sell_tax',None)
        if (not buy_tax) or (not sell_tax):
            return
        if (is_honeypot == "0") and (can_take_back_ownership == "0"):
            if (float(buy_tax) < 0.048) and (float(sell_tax) < 0.048):
                # 总市值:供应量*价格
                total_value = float(data['total_supply'])*ori_data['up']
                ori_data['total_value'] = total_value
                format_content = gen_msg(ori_data)
                sender(format_content,self.lark_bot_url,'dexfilter')
            else:
                logger.info(f'{token}买卖税率过大')
        else:
            logger.info(f'{token}不满足貔貅或者收回所有权')

    def consumer(self):
        """
        执行当前批次的列表页产生的任务，采集详情
        执行完跳出循环
        """
        num = 0
        while True:
            data = self.redis_cli.spop(self.redis_list_key)
            if data:
                data = json.loads(data)
                if 'nt' not in data:
                    logger.warning(f'没有nt：{data}')
                    continue
                # It is very strange ,sometimes  errors occurs but sometimes not in data sructure
                # but l can not reproduce the error,it will be nomal
                # so pass the coinsadjust
                try:
                    # 早期造富
                    if data['nt'] == 1:
                        self.check_flaw(data)
                    # 小市值
                    else:
                        self.req_total_value(data)
                        # “0”表示否的意思
                except:
                    logger.error(format_exc())
            else:
                # 每10分钟打印一次日志
                num += 1
                if num % 200 == 0:
                    logger.warning('当前任务执行完毕,等待新任务进来')
                time.sleep(3)