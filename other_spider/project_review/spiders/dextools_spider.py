from curl_cffi import requests
import logging
import json
import time
from datetime import datetime
from math import ceil
from retry import retry
from utils.redisdb import redis_cli
from .cmc_spider import Cmc
from .goplus import GoplusRisk
from other_spider.project_review.utils.limit_bio_length import cut_bio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review Dextools Spider')

class Dextools:
    """
    dextools爬虫
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.dextools_search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        # 传入pairaddres 和chain
        self.locks_data_url = 'https://www.dextools.io/shared/data/pair?address={}&chain={}&audit=true&locks=true'
        self.cookies_store = 'bk-early:cookies'
        # 合约风险检测
        self.goplus_risk = GoplusRisk()

    @retry(tries=100, delay=3)
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
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101", cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101")

        logger.info(f'response code: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code} {url} {cookie_dict}')
        else:
            # 真能获取到数据再把cookie放回去
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
            # cookie超过有效期，那么就重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30 * 60:
                pass
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

    def get_locks_data(self, pair_address, chain):
        url = self.locks_data_url.format(pair_address, chain)
        res = self.req(url)
        if res:
            data = res.json()['data']
            locks = data[0].get('locks')
            if locks:
                unicrypt = locks['unicrypt']
                locks_data = unicrypt['locks']
                lock_content_all = ''
                for key in locks_data:
                    value = locks_data[key]
                    percent = value['percent']
                    unlockDate = value['unlockDate']
                    # locks = token.get('locks')
                    # if locks:
                    #     lock_percent = locks[0]['percent']
                    if percent:
                        percent = float(percent)
                        percent = round(percent, 2)
                    # unlockDate = locks[0]['unlockDate']
                    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
                    date_object = datetime.strptime(unlockDate, date_format)
                    timestamp = int(date_object.timestamp())
                    lock_days = ceil((timestamp - int(time.time()))/(24*60*60))
                    lock_content = f'锁仓比例：{percent}% 锁仓时间：{lock_days}天  '
                    lock_content_all += lock_content
                if lock_content_all:
                    return lock_content_all.strip()
        return '无'

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
                    '代币地址': address,
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
            if info:
                description = info.get('description')
                # 控制长度在150个字符
                description = cut_bio(description)
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
        token_address = data['id']['token']
        pair_address = data['id']['pair']
        chain = data['id']['chain']
        symbol = data['symbol']
        creationTime = data.get('creationTime')
        if creationTime:
            creationTime = creationTime.replace('.000Z','').replace('T',' ')
        name = data['name']
        dextools_url = f'https://www.dextools.io/app/cn/{chain}/pair-explorer/{token_address}'
        result = {
            'base_info': {
                '代币名称': name,
                '代币符号': symbol,
                '创建时间': creationTime,
                '公链': chain,
                '代币地址': token_address,
                '项目描述': description
            },
            "chain_data": {
                "总市值": self.num_transform(TOTALMKTCAP),
                "流动市值":self.num_transform(MARKETCAP),
                "流动池": self.num_transform(LIQUIDITY),
                "代币持有人数": self.num_transform(HOLDERS),
                "24h dex交易量": self.num_transform(VOLUME24H),
                "24h 交易笔数":self.num_transform(Txs24H),
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
        if chain != 'solana':
            try:
                lock_content = self.get_locks_data(pair_address, chain)
                result['chain_data']['锁仓情况'] = lock_content
            except:
                logger.error(f'锁仓情况数据获取异常：{pair_address} {chain}')
        # 截止2024年03月21号 goplus不支持solana
        # if chain == 'solana':
        #     result['chain_data']['合约风险goplus'] = 'goplus不支持solana'
        if chain != 'solana':
            # 拼接合约风险信息
            try:
                goplus_risk_content = self.goplus_risk.check_risk(token_address, chain)
                # 成功请求
                if goplus_risk_content:
                    contract_risk = goplus_risk_content[0]
                    if contract_risk:
                        result['chain_data']['合约风险goplus'] = contract_risk
                    else:
                        result['chain_data']['合约风险goplus'] = '无'
                        logger.info(f'无合约风险goplus：{token_address} {chain}')
                    result['link']['goplus_url'] = goplus_risk_content[1]
            except:
                logger.error(f'合约风险检测异常goplus，{token_address} {chain}')
                result['chain_data']['合约风险goplus'] = '合约goplus检测异常，请联系管理员排查（提交您的URL）'
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