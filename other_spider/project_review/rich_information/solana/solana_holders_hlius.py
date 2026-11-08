import requests
import json
import logging
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Hlius API')

class Hlius:

    def __init__(self):
        self.api = "https://mainnet.helius-rpc.com/?api-key=537dd610-cdf6-45db-826c-918e0941cf0a"

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 万亿
        if num > 1000000000000:
            num = round((num / 1000000000000), 2)
            num = f'{num}T'
        # 10亿 转换成xxB
        elif num > 1000000000:
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

    @retry(tries=3, delay=6)
    def req(self, page, token_address):
        """
        请求接口获取1000条持币钱包地址
        """
        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "jsonrpc": "2.0",
            "method": "getTokenAccounts",
            "id": "helius-test",
            "params": {
                "page": page,
                "limit": 1000,
                "displayOptions": {},
                "mint": token_address
            }
        }
        logger.info(f'POST: page {page} address {token_address}')
        response = requests.post(self.api, headers=headers, data=json.dumps(payload), proxies=proxies)
        logger.info(f'Response {response.status_code}: page {page} address {token_address}')
        if response.status_code != 200:
            raise Exception(f'响应码错误 {response.status_code}，准备重试...')
        data = response.json()
        return data

    def sorted_addresses(self, holders, supply):
        """
        对持币地址根据持仓量进行排序
        返回格式化后的TOP10持币地址
        """
        sorted_list_holders = list(reversed(sorted(holders.items(), key=lambda x:x[1])))
        top10_holders = []
        head_content = '👇\n'
        for index, item in enumerate(sorted_list_holders):
            if index > 9:
                break
            address = item[0]
            amount_percent = round((item[1]/supply)*100, 2)
            hold_content = f'<i>        {address}  {amount_percent}%</i>'
            top10_holders.append(hold_content)

        addresses = '\n'.join(top10_holders)
        content = head_content + addresses
        return content

    def get_token_accounts(self, token_address):
        """
        获取代币的所有持币钱包地址
        """
        # 存放所有地址和持有量数据
        holders = {}
        # 总流通量
        supply = 0
        # 页码
        page = 1
        while True:
            # 根据页码请求1000条地址数据
            data = self.req(page, token_address)
            if not data:
                logger.error(f'接口请求异常，未获取到数据：page {page} address {token_address}')
                break
            token_accounts = data['result']['token_accounts']
            # 对原始数据进行转换
            for holder in token_accounts:
                amount = holder['amount']
                frozen = holder['frozen']
                owner = holder['owner']
                if not frozen:
                    supply += amount
                    holders[owner] = amount
            # 跳出翻页的条件
            if len(token_accounts) < 1000:
                print(f'共{page}页')
                break
            page+=1
        # TOP10持币地址
        alert_content = self.sorted_addresses(holders, supply)
        return alert_content

    def top10_addresses(self, data):
        """
        将持币地址TOP10数据拼接到原始数据
        """
        address = data['base_info']['代币地址']
        chain = data['base_info']['公链']
        need_spider_status = False
        # 必须得是solana链
        if chain == 'solana':
            # 持币地址可以通过多渠道获取，quickintel 不支持solana链，考虑从其他渠道获取
            if '持币地址' not in data['chain_data']:
                need_spider_status = True
            else:
                if data['chain_data']['持币地址'] == 'solana':
                    need_spider_status = True
        # 判断是否需要采集持币地址数据
        if need_spider_status:
            holders_content = self.get_token_accounts(address)
            data['chain_data']['持币地址'] = holders_content
            data['link']['birdeye'] = f'https://birdeye.so/token/{address}?chain=solana'
        else:
            logger.info(f'不需要采集solana TOP10持币地址信息')
        return data