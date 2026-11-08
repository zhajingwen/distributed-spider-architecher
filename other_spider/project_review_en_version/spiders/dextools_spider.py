from curl_cffi import requests
import logging
import json
import time
from functools import wraps
from traceback import format_exc
from datetime import datetime
from math import ceil
from utils.redisdb import redis_cli
from .cmc_spider import Cmc
from .goplus import GoplusRisk

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review Dextools Spider')

class Dextools:
    """
    dextools爬虫
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.dextools_search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        self.cookies_store = 'bk-early:cookies'
        # 合约风险检测
        self.goplus_risk = GoplusRisk()

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
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def req(self, url):
        """
        通过搜索接口获取到代币的详情
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        headers = {
            "Referer": "https://www.dextools.io/app/cn/pairs",
            'User-Agent': cookie_dict['ua'],
        }
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        logger.info(f'request: {url}')
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            # res = requests.get(url, headers=headers, proxies=proxies, cookies=cookies)
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101", cookies=cookies)
        else:
            # res = requests.get(url, headers=headers, proxies=proxies)
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101")
        logger.info(f'response code: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code} {url} {cookie_dict}')
        else:
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hold
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
            if (int(time.time()) - timestamp) > 30 * 60:
                pass
                # logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num/1000000000),2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num/1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    def get_detail_data(self, address):
        """
        从dextools获取代币详情
        """
        url = self.dextools_search_url.format(address)
        res = self.req(url)
        data = res.json()['results']
        if not data:
            result = {
                'base_info': {
                    'token_address': address,
                    '警告': '该币dextools未收录，无法提供更多维度的信息'
                },
                "chain_data": {
                },
                "social": {},
                "link": {
                }
            }
            return result
        data = data[0]
        TOTALMKTCAP = None
        MARKETCAP = None
        HOLDERS = None
        WEBSITE = None
        TWITTER = None
        TELEGRAM = None
        DISCORD = None
        price = data.get('price')
        token = data.get('token')
        token_metrics = None
        totalSupply = None
        circulatingSupply = None
        links = None
        description = None
        lock_percent = None
        if token:
            token_metrics = token.get('metrics')
            links = token.get('links')
            info = token.get('info')
            locks = token.get('locks')
            if locks:
                lock_percent = locks[0]['percent']
                if lock_percent:
                    lock_percent = round(lock_percent, 2)
                unlockDate = locks[0]['unlockDate']
                date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
                date_object = datetime.strptime(unlockDate, date_format)
                timestamp = int(date_object.timestamp())
                lock_days = ceil((timestamp - int(time.time()))/(24*60*60))
            if info:
                description = info.get('description')
        if token_metrics:
            totalSupply = token_metrics.get('totalSupply')
            circulatingSupply = token_metrics.get('circulatingSupply')
        if price and totalSupply:
            # circulatingSupply
            TOTALMKTCAP = price*totalSupply
        if price and circulatingSupply:
            MARKETCAP = price*circulatingSupply
        LIQUIDITY = data['metrics']['liquidity']
        if token_metrics:
            HOLDERS = token_metrics.get('holders')
        VOLUME24H = data.get('volume')
        Txs24H = data.get('swaps')
        if links:
            WEBSITE = links.get('website')
            TWITTER = links.get('twitter')
            TELEGRAM = links.get('telegram')
            DISCORD = links.get('discord')
        token_address1 = data['id']['token']
        token_address2 = data['id']['pair']
        # cmc可能是大写，而dextools是小写
        address = address.lower()
        if token_address1 == address:
            token_address = token_address1
        else:
            token_address = token_address2
        chain = data['id']['chain']
        symbol = data['symbol']
        creationTime = data.get('creationTime')
        if creationTime:
            creationTime = creationTime.replace('.000Z','').replace('T',' ')
        name = data['name']
        # result = {
        #     'name': name,
        #     'symbol': symbol,
        #     'creationTime': creationTime,
        #     'chain': chain,
        #     'token_address': token_address,
        #     "total_mktcap": self.num_transform(TOTALMKTCAP),
        #     "mktcap":self.num_transform(MARKETCAP),
        #     "liquidity": self.num_transform(LIQUIDITY),
        #     "holders": self.num_transform(HOLDERS),
        #     "volume24h_dex": self.num_transform(VOLUME24H),
        #     "24h_txs":self.num_transform(Txs24H),
        #     "website":WEBSITE,
        #     "twitter":TWITTER,
        #     "telegram":TELEGRAM,
        #     "discorad":DISCORD,
        #     'description':description
        # }
        dextools_url = f'https://www.dextools.io/app/cn/{chain}/pair-explorer/{token_address}'
        result = {
            'base_info': {
                'name': name,
                'symbol': symbol,
                'creationTime': creationTime,
                'chain': chain,
                'token_address': token_address,
                'description': description
            },
            "chain_data": {
                "total_mktcap": self.num_transform(TOTALMKTCAP),
                "mktcap":self.num_transform(MARKETCAP),
                "liquidity": self.num_transform(LIQUIDITY),
                "holders": self.num_transform(HOLDERS),
                "volume24h_dex": self.num_transform(VOLUME24H),
                "24h_txs":self.num_transform(Txs24H),
            },
            "social": {},
            "link": {
                "website":WEBSITE,
                "twitter":TWITTER,
                "telegram":TELEGRAM,
                "discoard":DISCORD,
                'dextools_url':dextools_url
            }
        }
        if lock_percent:
            result['chain_data']['lock_percent'] = lock_percent
            result['chain_data']['lock_days'] = lock_days
        # 拼接合约风险信息
        try:
            goplus_risk_content = self.goplus_risk.check_risk(address, chain)
            # 成功请求
            if goplus_risk_content:
                contract_risk = goplus_risk_content[0]
                if contract_risk:
                    result['chain_data']['contract_risk'] = contract_risk
                else:
                    result['chain_data']['contract_risk'] = '无'
                    logger.info(f'无合约风险：{address} {chain}')
                result['link']['goplus_url'] = goplus_risk_content[1]
        except:
            logger.error(f'合约风险检测异常，{address} {chain}')
            result['chain_data']['contract_risk'] = '合约检测异常，请联系管理员排查（提交您的URL）'
        return result

    def coin_info_polymeric(self, address):
        """
        获取代币所有相关信息 （聚合多网站信息）
        return: dict dextools + goplus + cmc
        """
        # dict
        dextools_detail_data = self.get_detail_data(address)
        # 通过CMC来获取上线CEX的情况,如果上线给字典新增cex清单，和cex全部市场交易额，和每个cex的具体交易额
        combined_cmc_and_dextools_data = Cmc().inherit_dextools(dextools_detail_data)
        if combined_cmc_and_dextools_data:
            return combined_cmc_and_dextools_data
        # 未上线cex
        else:
            return dextools_detail_data

    def run_url(self, url):
        """
        解析URL，并且采集数据
        样例URL：https://www.dextools.io/app/cn/bnb/pair-explorer/0xAD5D013A307d6DC3aA2A1c908633a69813c8a282
        return: dict 聚合多网站的代币信息 dextools + cmc + goplus
        """
        if 'pair-explorer' not in url:
            content = '输入的URL有误'
            return content
        # 代币地址
        address = url.strip().split('/')[-1]
        if '?' in address:
            address = address.split('?')[0]
        return self.coin_info_polymeric(address)

    def run_address(self, address):
        """
        处理输入的消息是合约地址
        """
        if len(address) == 42:
            return self.coin_info_polymeric(address)