import requests
import time
import os
import logging
from utils.proxy_requests import proxies
from traceback import format_exc
from retry import retry
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Trendx')
env = os.environ.get('env')

class TrendxAlert:
    def __init__(self):
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        # get请求，无鉴权，热度值排序
        # self.url = 'https://app.trendx.tech/v1/dao/public/projects/stars?sendType=sendCoin&sort=heat1&order=2&page=1&rows=20'
        self.url = 'https://app.trendx.tech/v1/dao/public/projects/stars?sort=heat1&order=2&page=1&rows=20'
        self.lark_webhook = os.getenv('LARK_WEBHOOK_TWITTERSCAN', '')

    @retry(tries=6, delay=3)
    def req_trending(self):
        """
        发起trending tokens 请求
        """
        logger.info(f'GET: {self.url}')
        res = requests.get(self.url, headers=self.headers,proxies=proxies)
        # res = requests.get(self.url, headers=self.headers)
        try:
            self.parse_trending(res)
        except:
            logger.error(format_exc())
            logger.error('trending解析异常')
        logger.info(f'response {res.status_code}: {self.url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常 {res.status_code}')

    def parse_trending(self, response):
        """
        解析trending tokens
        """
        data = response.json()
        rows = data['data']['rows']
        content = ''
        for index, item in enumerate(rows):
            fullName = item['fullName']
            heat1 = item['heat1']
            twitterFollowers = item['twitterFollowers']
            row_c = f'项目名：{fullName} 热度：{heat1} X粉丝量：{twitterFollowers}\n'
            content += row_c

        sender(content, self.lark_webhook, '热度前10')

    def run(self):
        while True:
            self.req_trending()
            # 6小时推送一次
            time.sleep(6*60*60)