import requests
import logging
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Geniidata Gas')

class GasSpider:
    def __init__(self):
        self.gas_api = 'https://mempool.space/api/v1/fees/recommended'
        # self.hot_assets_api = 'https://www.geniidata.com/api/btc/ord/flow/minters?type=1D&p=brc20'
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }

    @retry(tries=3, delay=6)
    def req(self, url):
        """
        发起请求拿数据
        """
        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        # res = requests.get(url, headers=self.headers)
        logger.info(f'Response: {res.status_code}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        return res

    def gas(self):
        """
        拿到gas数据
        """
        response = self.req(self.gas_api)
        data = response.json()
        halfHourFee = data['halfHourFee']
        return halfHourFee
