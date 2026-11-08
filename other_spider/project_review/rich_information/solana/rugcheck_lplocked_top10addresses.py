import requests
import logging
from traceback import format_exc
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Rugcheck Spider')

class Rugcheck:
    def __init__(self):
        # 该接口同时能够提供锁仓情况和Top holders情况等诸多链上数据
        self.api = "https://api.rugcheck.xyz/v1/tokens/{}/report"

    @retry(tries=3, delay=6)
    def req(self, token_address):
        """
        请求接口获取1000条持币钱包地址
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        url = self.api.format(token_address)
        logger.info(f'GET {url}')
        response = requests.get(url, headers=headers, proxies=proxies)
        logger.info(f'Response {response.status_code}: {token_address}')
        if response.status_code != 200:
            raise Exception(f'响应码错误 {response.status_code}，准备重试...')
        data = response.json()
        return data

    def lplocked_percent(self, data, rugcheck_response_data):
        """
        获取锁仓比例数据
        """
        address = data['base_info']['代币地址']
        chain = data['base_info']['公链']
        # 必须得是solana链
        if chain == 'solana':
            # item = self.req(address)
            lpLockedPct = rugcheck_response_data['markets'][0]['lp']['lpLockedPct']
            lock_content = f'锁仓比例：{lpLockedPct}%'
            data['chain_data']['锁仓情况'] = lock_content
            link = f'https://rugcheck.xyz/tokens/{address}'
            data['link']['rugcheck'] = link
        return data

    def parse_top_addresses(self, data_response):
        """
        截取前十持仓地址，并拼接成指定格式
        """
        topHolders = data_response['topHolders']
        top10_holders = []
        head_content = '👇\n'
        for index, item in enumerate(topHolders):
            if index > 9:
                break
            address = item['address']
            pct = item['pct']
            amount_percent = round(pct, 2)
            hold_content = f'<i>        {address}  {amount_percent}%</i>'
            top10_holders.append(hold_content)

        addresses = '\n'.join(top10_holders)
        content = head_content + addresses
        return content

    def top10_addresses(self, data, rugcheck_response_data):
        """
        将持币地址TOP10数据拼接到原始数据
        """
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
            holders_content = self.parse_top_addresses(rugcheck_response_data)
            data['chain_data']['持币地址'] = holders_content
        else:
            logger.info(f'不需要采集solana TOP10持币地址信息')
        return data

    def lplocked_percent_mixed_top10_addresses(self, data):
        """
        1、获取锁仓比例数据
        2、TOP 10 持仓地址
        """
        address = data['base_info']['代币地址']
        rugcheck_response_data = self.req(address)
        try:
            # 获取锁仓比例数据
            data = self.lplocked_percent(data, rugcheck_response_data)
        except:
            logger.error(format_exc())
        try:
            # TOP 10 持仓地址
            data = self.top10_addresses(data, rugcheck_response_data)
        except:
            logger.error(format_exc())
        return data
