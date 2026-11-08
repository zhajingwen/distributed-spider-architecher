import os
import logging
import time
import json
from curl_cffi import requests
from datetime import datetime, timedelta
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.mongrel_dog.lark_bot import sender
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mongrel Dog User_a Plus')

class Consumer:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.user_a_jobs = 'mongrel:user_a:jobs'
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.webhook_api = os.getenv('LARK_WEBHOOK_MONGREL_DOG_USER_A', '')
        self.dextools_search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        self.cookies_store = 'bk-early:cookies'

    def transfer_digital_num(self, num):
        """
        将数值转换成携带单位的M结尾，或者K结尾
        """
        if int(num)/1000000 > 1:
            num = f'{round(int(num)/1000000,2)}M'
        else:
            if int(num)/1000 > 1:
                num = f'{round(int(num)/1000, 2)}K'
        return num

    def content_base(self, dexscreener):
        """
        拼接告警内容
        """
        data = dexscreener
        name = data['baseToken']['name']
        price = data['priceUsd']
        priceChange_h6 = data['priceChange']['h6']
        priceChange_h24 = data['priceChange']['h24']
        volume = data['volume']['h24'] / 1000000
        volume = round(volume, 3)
        pairAddress = data['pairAddress']
        chainId = data['chainId']
        if chainId == 'ethereum':
            chainId = 'ether'
        if chainId == 'bsc':
            chainId = 'bnb'
        # url = f'https://dexscreener.com/{chainId}/{pairAddress}'
        url = f'https://www.dextools.io/app/cn/{chainId}/pair-explorer/{pairAddress}'
        marketCap = data['marketCap']
        marketCap = self.transfer_digital_num(marketCap)
        txns = data['txns']
        trx_1h = txns['h1']['buys'] + txns['h1']['sells']
        liquidity = int(data['liquidity']['usd'])
        liquidity = self.transfer_digital_num(liquidity)
        content = f"""代币名称: {name}

        1、 当前价格：${price}
        2、 6小时涨幅：{priceChange_h6}%
        3、 24小时涨幅：{priceChange_h24}%
        4、 交易量：{volume} M
        5、 DEXTools：{url}
        6、 市值：{marketCap}
        7、 1小时交易笔数：{trx_1h}
        8、 liquidity：{liquidity}
        """
        return content

    @retry(tries=100, delay=3)
    def req(self, url):
        logger.info(f'GET {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies, impersonate="chrome101")
        logger.info(f'Response {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        # else:
        #     self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res.json()

    def is_online_cex(self, address):
        """
        通过cmc查询是否上线了中心化交易所
        """
        # cmc接受地址的小写形式
        # address = address.lower()
        # 获取CMC能够查到的全部币种信息
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        data = self.req(url)
        slug = None
        for item in data['values']:
            if len(item) >= 7:
                # list
                cmc_addresses = item[7]
                # cmc 地址大小写标准很混乱，下面是为了做各种兼容
                if address in cmc_addresses:
                    slug = item[3]
                else:
                    if address.lower() in cmc_addresses:
                        slug = item[3]
                    else:
                        if cmc_addresses:
                            # 可能在列表中第二个元素且大小写不一致
                            for a in cmc_addresses:
                                a = a.lower()
                                if address.lower() == a:
                                    slug = item[3]
        if not slug:
            logger.error(f'该币在CMC查询不到：{address}')
            return
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=10&category=spot&centerType=cex&sort=cmc_rank_advanced'
        data = self.req(url)
        data = data['data']
        # 当没有中心化交易所的时候该key可能不存在
        marketPairs = data['marketPairs']
        if marketPairs:
            logger.info(f'已上线cex交易所：{marketPairs}')
            exchangeNames = []
            for i in marketPairs:
                exchangeName = i['exchangeName']
                if exchangeName not in exchangeNames:
                    exchangeNames.append(exchangeName)
            return '\n'.join(exchangeNames)
            # return marketPairs
        else:
            logger.info(f'查询到的交易所列表为空：{marketPairs}')
            return False

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
                logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry(tries=6, delay=6)
    def req_dextools(self, url):
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
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101", cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101")
        logger.info(f'response code: {res.status_code} {url}')
        logger.info(f'request headers {res.request.headers}')
        if res.status_code == 403:
            logger.warning(f'cookies 有问题，准备切换')
            return
        return res

    def get_pool_created_time(self, address):
        """
        从dextools获取池子创建时间
        """
        url = self.dextools_search_url.format(address)
        logger.info(f'request: {url}')
        # 对于403状态码进行重试
        num = 0
        while True:
            num += 1
            res = self.req_dextools(url)
            if res:
                break
            else:
                logger.info(f'cookies故障，切换 {num}')
        data = res.json()['results'][0]
        creationTime = data['creationTime']
        return creationTime

    def price_increased_filter(self, dexscreener):
        """
        6小时涨幅>1%，24小时涨幅>10%
        满足涨幅需求返回True
        """
        priceChange_h6 = dexscreener['priceChange']['h6']
        priceChange_h24 = dexscreener['priceChange']['h24']
        if priceChange_h6 > 1 and priceChange_h24 > 10:
            return True
        else:
            logger.info(f'不满足涨幅要求，过滤！{dexscreener}')
            return False


    def risk(self, goplus):
        """
        输出代币风险
        return: str 合约风险信息
        """
        all_status = []
        is_mintable = goplus.get('is_mintable', 0)
        cannot_buy = goplus.get('cannot_buy', 0)
        cannot_sell_all = goplus.get('cannot_sell_all', 0)
        honeypot_with_same_creator = goplus.get('honeypot_with_same_creator', 0)
        is_in_dex = goplus.get('is_in_dex', 0)
        is_open_source = goplus.get('is_open_source', 0)
        is_proxy = goplus.get('is_proxy', 0)
        anti_whale_modifiable = goplus.get('anti_whale_modifiable', 0)
        can_take_back_ownership = goplus.get('can_take_back_ownership', 0)
        external_call = goplus.get('external_call', 0)
        hidden_owner = goplus.get('hidden_owner', 0)
        is_blacklisted = goplus.get('is_blacklisted', 0)
        is_honeypot = goplus.get('is_honeypot', 0)
        # is_mintable = goplus.get('is_mintable', 0)
        is_whitelisted = goplus.get('is_whitelisted', 0)
        owner_balance = goplus.get('owner_balance', 0)
        owner_change_balance = goplus.get('owner_change_balance', 0)
        personal_slippage_modifiable = goplus.get('personal_slippage_modifiable', 0)
        selfdestruct = goplus.get('selfdestruct', 0)
        slippage_modifiable = goplus.get('slippage_modifiable', 0)
        trading_cooldown = goplus.get('trading_cooldown', 0)
        transfer_pausable = goplus.get('transfer_pausable', 0)
        # slippage_modifiable = goplus.get('slippage_modifiable', 0)


        if int(is_mintable) == 1:
            is_mintable = '可增发'
            all_status.append(is_mintable)
        if int(cannot_buy) == 1:
            cannot_buy = '不可买入'
            all_status.append(cannot_buy)
        if int(cannot_sell_all) == 1:
            cannot_sell_all = '不可全部卖出'
            all_status.append(cannot_sell_all)
        if int(is_open_source) == 0:
            is_open_source = '没开源'
            all_status.append(is_open_source)
        if int(is_proxy) == 1:
            is_proxy = '有代理合约'
            all_status.append(is_proxy)
        if int(anti_whale_modifiable) == 1:
            anti_whale_modifiable = '反巨鲸可修改'
            all_status.append(anti_whale_modifiable)
        if int(can_take_back_ownership) == 1:
            can_take_back_ownership = '能取回所有权'
            all_status.append(can_take_back_ownership)
        if int(external_call) == 1:
            external_call = '存在外部调用'
            all_status.append(external_call)
        if int(hidden_owner) == 1:
            hidden_owner = '存在隐藏owner'
            all_status.append(hidden_owner)
        if int(is_blacklisted) == 1:
            is_blacklisted = '存在黑名单机制'
            all_status.append(is_blacklisted)
        if int(is_honeypot) == 1:
            is_honeypot = '貔貅盘'
            all_status.append(is_honeypot)
        if int(is_whitelisted) == 1:
            is_whitelisted = '存在白名单机制'
            all_status.append(is_whitelisted)
        if int(owner_change_balance) == 1:
            owner_change_balance = 'owner可修改余额'
            all_status.append(owner_change_balance)
        if int(personal_slippage_modifiable) == 1:
            personal_slippage_modifiable = '滑点可修改'
            all_status.append(personal_slippage_modifiable)
        if int(selfdestruct) == 1:
            selfdestruct = '可自毁'
            all_status.append(selfdestruct)
        if int(slippage_modifiable) == 1:
            slippage_modifiable = '滑点可修改'
            all_status.append(slippage_modifiable)
        if int(trading_cooldown) == 1:
            trading_cooldown = '交易可冷却'
            all_status.append(trading_cooldown)
        if int(transfer_pausable) == 1:
            transfer_pausable = '交易可暂停'
            all_status.append(transfer_pausable)
        if not all_status:
            return ''
        content = ','.join(all_status)
        return content

    def task_process(self, job):
        """
        处理任务
        """
        job = json.loads(job)
        # 来自dexscreener的数据
        dexscreener = job['dexscreener']

        # 检测是否满足涨幅需求 决定是否做报警推送
        if not self.price_increased_filter(dexscreener):
            logger.info('不满足涨幅要求过滤')
            return

        # 基础告警内容，aaron版本
        content_base = self.content_base(dexscreener)

        # 来自goplus的数据
        goplus = job['goplus']

        buy_tax = goplus['buy_tax']
        if buy_tax:
            buy_tax = f'{float(buy_tax)*100}%'
        sell_tax = goplus['sell_tax']
        if sell_tax:
            sell_tax = f'{float(sell_tax)*100}%'
        try:
            cex_status = self.is_online_cex(dexscreener['baseToken']['address'])
        except:
            cex_status = None
        if cex_status:
            cex_status = f"CEX清单：\n\n{cex_status}\n\n"
        else:
            cex_status = '未上线CEX'
        holder_count = goplus['holder_count']
        # 24H交易笔数
        txns_h24 = dexscreener['txns']['h24']
        buys_h24 = txns_h24['buys']
        sells_h24 = txns_h24['sells']
        transactions_24h = buys_h24 + sells_h24
        # 从dextools获取池子创建时间
        pairAddress = dexscreener['pairAddress']

        creationTime = self.get_pool_created_time(pairAddress)
        # 将字符串转换为 datetime 对象
        date = datetime.strptime(creationTime, "%Y-%m-%dT%H:%M:%S.%fZ")
        # 添加8小时的时差（东八区）
        date_eastern = date + timedelta(hours=8)
        # 格式化为指定的时间字符串
        formatted_date = date_eastern.strftime("%Y/%m/%d %H:%M")
        risk = self.risk(goplus)
        # chainId = dexscreener['chainId']
        new_content = f"""9、合约问题：买入税率：{buy_tax}，卖出税率：{sell_tax}，{risk}
        10、代币持有人数：{holder_count}
        11、上线交易所情况：{cex_status}
        12、合约地址：{dexscreener['baseToken']['address']}
        13、24小时交易笔数：{transactions_24h}
        14、dex上创建时间：{formatted_date}
        """
        content = content_base + new_content
        sender(content,url=self.webhook_api)

    def consumer(self):
        """
        消费Aaron早起造富推送过来的任务
        """
        while True:
            job = self.redis_cli.spop(self.user_a_jobs)
            if job:
                self.task_process(job)
            else:
                time.sleep(6)

