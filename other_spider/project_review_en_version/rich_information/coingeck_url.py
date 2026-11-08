import requests
import logging
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Url Match')

class CoingeckSearch:
    def __init__(self, symbol):
        self.symbol = symbol
        self.api = 'https://www.coingecko.com/en/search_v2?query={}'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }

    @retry(tries=3, delay=3)
    def match(self):
        """
        根据symbol发起搜索请求
        """
        if self.symbol:
            url = self.api.format(self.symbol)
            logger.info(f'Request: {url}')
            res = requests.get(url, headers=self.headers, proxies=proxies)
            logger.info(f'Response: {res.status_code} {url}')
            if res.status_code == 200:
                data = res.json()
                coins = data['coins']
                if coins:
                    coin = coins[0]
                    id = coin['id']
                    coingecko_match_url = f'https://www.coingecko.com/en/coins/{id}'
                    return coingecko_match_url
        return

    def get_url(self):
        try:
            url = self.match()
            return url
        except:
            return