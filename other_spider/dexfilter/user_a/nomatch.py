import time
import requests
import logging
import json
import queue

import re
from copy import deepcopy
from urllib.parse import urlencode
from traceback import format_exc
# from .data_filter import Filter
from other_spider.dexfilter.spiders.retry import retry,retry_net
from threading import Thread
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('USER_A SPIDER')



class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class NoMatch:
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
        self.redis_tradeinfo_jobkey = 'dexfilter:user_a:tradeinfo'
        self.redis_poolinfo_jobkey = 'dexfilter:user_a:poolinfo'
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
        self.chain_info = {'eth': {'website': {'link': 'https://etherscan.io/address/', 'hashLink': 'https://etherscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.uniswap.org/#/swap', 'title': 'Transaction'}}, 'bsc': {'website': {'link': 'https://bscscan.com/address/', 'hashLink': 'https://bscscan.com/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://pancakeswap.finance/swap?outputCurrency=', 'title': 'Transaction'}}, 'pol': {'website': {'link': 'https://polygonscan.com/address/', 'hashLink': 'https://polygonscan.com/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://quickswap.exchange/#/swap', 'title': 'Transaction'}}, 'ava': {'website': {'link': 'https://snowtrace.io/address/', 'hashLink': 'https://snowtrace.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://traderjoexyz.com/trade#/', 'title': 'Transaction'}}, 'avax': {'website': {'link': 'https://snowtrace.io/address/', 'hashLink': 'https://snowtrace.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://traderjoexyz.com/trade#/', 'title': 'Transaction'}},'fan': {'website': {'link': 'https://ftmscan.com/address/', 'hashLink': 'https://ftmscan.com/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://spooky.fi/#/swap', 'title': 'Transaction'}}, 'cro': {'website': {'link': 'https://cronoscan.com/address/', 'hashLink': 'https://cronoscan.com/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://mm.finance/swap', 'title': 'Transaction'}}, 'aur': {'website': {'link': 'https://aurorascan.dev/address/', 'hashLink': 'https://aurorascan.dev/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://www.trisolaris.io/#/swap', 'title': 'Transaction'}}, 'mri': {'website': {'link': 'https://moonriver.moonscan.io/address/', 'hashLink': 'https://moonriver.moonscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.solarbeam.io/zh-CN/exchange/swap', 'title': 'Transaction'}}, 'mbe': {'website': {'link': 'https://moonbeam.moonscan.io/address/', 'hashLink': 'https://moonbeam.moonscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://spooky.fi/#/swap', 'title': 'Transaction'}}, 'arb': {'website': {'link': 'https://arbiscan.io/address/', 'hashLink': 'https://arbiscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.uniswap.org/#/swap', 'title': 'Transaction'}}, 'opt': {'website': {'link': 'https://optimistic.etherscan.io/address/', 'hashLink': 'https://optimistic.etherscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.uniswap.org/#/swap', 'title': 'Transaction'}}, 'dog': {'website': {'link': 'https://explorer.dogechain.dog/address/', 'hashLink': 'https://explorer.dogechain.dog/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://www.kibbleswap.dog/swap?to=', 'title': 'Transaction'}}, 'gno': {'website': {'link': 'https://gnosisscan.io/address/', 'hashLink': 'https://gnosisscan.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://honeyswap.1hive.eth.limo/#/swap', 'title': 'Transaction'}}, 'cel': {'website': {'link': 'https://explorer.celo.org/mainnet/address/', 'hashLink': 'https://explorer.celo.org/mainnet/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.ubeswap.org/#/swap', 'title': 'Transaction'}}, 'met': {'website': {'link': 'https://andromeda-explorer.metis.io/address/', 'hashLink': 'https://andromeda-explorer.metis.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://netswap.io/#/swap', 'title': 'Transaction'}}, 'hec': {'website': {'link': 'https://www.hecoinfo.com/en-us/address/', 'hashLink': 'https://www.hecoinfo.com/en-us/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://ht.mdex.com/#/swap?outputCurrency=', 'title': 'Transaction'}}, 'ast': {'website': {'link': 'https://blockscout.com/astar/address/', 'hashLink': 'https://blockscout.com/astar/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.arthswap.org/#/swap', 'title': 'Transaction'}}, 'can': {'website': {'link': 'https://evm.explorer.canto.io/address/', 'hashLink': 'https://evm.explorer.canto.io/tx/', 'title': 'website'}, 'Transaction': {'link': 'https://app.slingshot.finance/swap/ETH', 'title': 'Transaction'}}}
        self.excutor = MyThreadPoolExecutor(max_workers=20)
        self.rds = DataUtils('spider')

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
        cookie_dict = self.get_cookie()
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
        # 当响应码异常的时抛出异常让重试装饰器重试
        if res.status_code in [403,500,502,503,504]:
            logger.info(f'{cookie_dict} {res.status_code} err 准备重试...')
            raise Exception(f'{res.status_code}')
        if res.status_code != 200:
            logger.warning(f'status_code: {res.status_code} {url}  {cookie_dict}')
            return
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
        # url = f'https://dexfilter.com/v1/{chain}/index?{urlencode(params)}&page={page}'
        url = f'https://dexfilter.com/v1/{chain}/indexV1?{urlencode(params)}&page={page}'
        res = self.req(url)
        if not res:
            logger.warning(f'can not get data normally {url}')
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

    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

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
                        self.excutor.submit(self.req_detail,coin).add_done_callback(self.executor_callback)
                else:
                    logger.warning(f'当前无数据：{data}')
            else:
                logger.error(data)
        else:
            logger.error(data)

    def social(self, ori_data):
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
        # 发行量,部分发行量，数据格式不标准  代币供应量
        # 发行量：2320000000.000000000000000000，price：6.560754863045031e-05
        # {"status":true,"code":200,"msg":"success","data":{"up":0.09348035809309858,"ub":1266961.1040455592,"wb":836.5464878883279,"h":0.11301519754409158,"l":0.02213150530139481,"sum_vn":23637259.476673488,"chat":{"twitter":"https:\/\/twitter.com\/RDNTCapital","telegram":"https:\/\/t.me\/radiantcapitalofficial","discord":"https:\/\/discord.radiant.capital\/","web":"https:\/\/radiant.capital\/"},"name":"Radiant","symbol":"RDNT","supply":205171328.94843346,"token":"0x0C4681e6C0235179ec3D4F4fc4DF3d14FDD96017","holders":13519}}
        if result.json()['code'] != 200:
            return
        result = result.json()['data']
        # 可能是个空列表
        if not result:
            return
        ori_data.update(result)
        supply = result['supply']
        if not supply:
            return
        if type(supply) == str:
            supply = supply.split('.')[0]
            if not supply:
                return
        supply = int(supply)
        # 当前市场价
        price = result['up']
        logger.info(f'发行量：{supply}，price：{price}')
        # 总市值
        total_value = round(supply * price, 2)
        ori_data['total_value'] = total_value
        return ori_data

    @retry(1)
    def get_gas(self, ori_data):
        token = ori_data['token']
        chain = ori_data['chain']
        url = f'https://aywt3wreda.execute-api.eu-west-1.amazonaws.com/default/IsHoneypot?chain={chain}&token={token}'
        logger.info(f'request {url}')
        res = requests.get(url,headers=self.headers)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'response code error {res.status_code}')
        new_data = res.json()
        ori_data.update(new_data)
        return ori_data

    def req_detail(self, ori_data):
        ori_data = self.social(ori_data)
        if not ori_data:
            return
        try:
            ori_data = self.honeypot(ori_data)
        except:
            return
        # 可能为空
        data = self.get_gas(ori_data)
        if not data:
            return
        id = re.sub('^d', '', ori_data['tbname'])
        chain = ori_data['chain']
        is_honeypot = data.get('is_honeypot', "0")
        # 极少部门没有这个key
        holders = data.get('holders',0)
        candle_url = f'https://cronoscan.com/address/{id}'
        analysis_url = f'https://dexfilter.com/v1/cro/getRightInfo?tag={id}'
        coin_info = self.chain_info[chain]
        scan_url = coin_info['website']['link'] + data['token']
        tg_url = data['chat']['telegram']
        twitter_url = data['chat']['twitter']
        pool_url = coin_info['Transaction']['link']
        discord_url = data['chat']['discord']
        web_url = data['chat']['web']
        sell_tax = data.get('sell_tax','null')
        buy_tax = data.get('buy_tax','null')
        spider_dat_h = time.strftime("%Y-%m-%d %H", time.localtime(int(time.time())))
        BuyGas = data.get('BuyGas','null')
        if not BuyGas:
            BuyGas = 'null'
        SellGas = data.get('SellGas','null')
        if not SellGas:
            SellGas = 'null'
        BuyTax = data.get('BuyTax','null')
        if not BuyTax:
            BuyTax = 'null'
        SellTax = data.get('SellTax','null')
        if not SellTax:
            SellTax = 'null'
        supply = data.get('supply')
        if not supply:
            return
        supply = int(float(supply))
        # bigint 长度
        if supply > (pow(2,63)-1):
            logger.info(f'supply数值太大：{data["supply"]}')
            return
        sql = f"replace into dexfilter_user_a_a values ({repr(data['token'])},{repr(id)}," \
              f"{repr(data['chain'])},{repr(data['tn'])},{repr(data['sy'])},{data['up']}," \
              f"{data['pb']},{repr(candle_url)},{repr(analysis_url)},{repr(scan_url)}," \
              f"{repr(tg_url)},{repr(twitter_url)},{repr(pool_url)},{repr(discord_url)}," \
              f"{repr(web_url)},{data['wb']},{data['ub']},{data['total_value']},{data['supply']}," \
              f"{data['h']},{data['l']},{holders},{repr(is_honeypot)}," \
              f"{BuyGas},{SellGas},{BuyTax}," \
              f"{SellTax},{repr(data.get('is_mintable','null'))}," \
              f"{data.get('lp_holder_count','null')},{repr(data.get('is_anti_whale','null'))}," \
              f"{sell_tax},{buy_tax},{repr(data.get('slippage_modifiable','null'))}," \
              f"{repr(data.get('is_open_source','null'))},{repr(data.get('can_take_back_ownership','null'))}," \
              f"{repr(data.get('cannot_sell_all','null'))},{repr(data.get('trading_cooldown','null'))}," \
              f"{repr(data.get('transfer_pausable','null'))},{repr(data.get('is_blacklisted','null'))}," \
              f"{repr(data.get('is_proxy','null'))},{repr(data.get('is_whitelisted','null'))},{data['r5m']}," \
              f"{data['r1h']},{data['r4h']},{data['r24h']},{repr(spider_dat_h)});"
        data['id'] = id
        sql = sql.replace('None','null')
        self.rds.insert(sql)
        # put the coinsadjust to tradeinfo consumer
        self.redis_cli.sadd(self.redis_tradeinfo_jobkey, json.dumps(data))
        # put the coinsadjust into poolinfo consumer
        self.redis_cli.sadd(self.redis_poolinfo_jobkey, json.dumps(data))



    def honeypot(self, ori_data):
        """
        判断是否存在合约漏洞
        早期造富（3）和小市值（3）的规则不同，注意区分
        该请求可能没有返回值；看需求方是否需要丢掉该数据
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
            logger.warning(f'响应体为空: {url}')
            return ori_data
        result = result.json()
        if not result:
            return
        if not result['result']:
            logger.info(f'貔貅该token响应体为空 {ori_data}')
            return ori_data
        # 注意token要转化成小写
        data = result['result'][token.lower()]
        if 'holders' in data:
            data.pop('holders')
        ori_data.update(data)
        return ori_data


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
                self.req_list(chain, params)

    def run(self):
        """
        定时执行，每1小时跑一次
        """
        while True:
            self.allchains()
            logger.info('当前批次列表页执行完毕')
            time.sleep(60*60*1)

    def create(self):
        self.rds.create_table()