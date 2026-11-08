import requests
import logging
import time
import csv
from retry import retry
# from lxml import etree
from math import ceil
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('OKX SOLANA SMART MONEY')

class OkxSolana:
    """
    从下面网站采集融资信息
    https://crypto-fundraising.info/projects/Fusionist/
    """
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.base_api = 'https://www.okx.com/priapi/v1/invest/activity/smart-money/list?pageNo={}&t={}'
        self.total_addresses = 2794
        file_name = 'smart_money.csv'
        self.csvfile = open(file_name, 'w', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.csvfile)
        title = ['地址', '7日胜率', '7日收益率']
        self.writer.writerow(title)
        logger.info('标题已写入csv')

    @retry(tries=4, delay=3)
    def req(self, url):
        """
        请求列表页数据
        """
        logger.info(f'GET {url}')
        # res = requests.get(url=url, headers=self.headers, proxies=proxies)
        res = requests.get(url=url, headers=self.headers)
        logger.info(f'response {res.status_code} url')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {url}')
        origin_data = res.json()
        data = origin_data.get('data')
        if not data:
            raise Exception(f'数据体异常：{res.status_code} {url} {origin_data}')
        result = data.get('result')
        if not result:
            raise Exception(f'数据体异常：{res.status_code} {url} {origin_data}')
        return result

    def parse(self, result, pagenum):
        """
        解析数据
        存入csv
        """
        for item in result:
            userAddress = item['userAddress']
            winRate = item['winRate']
            yieldRate = item['yieldRate']
            row = [userAddress, winRate, yieldRate]
            self.writer.writerow(row)
        if result:
            logger.info(f'该页csv写入成功：{pagenum}')

    def tast_one(self, url, pagenum):
        """
        处理每一页的数据
        """
        result = self.req(url)
        if result:
            self.parse(result, pagenum)
        else:
            logger.info(f'该页没有获取到数据：{pagenum}')

    def run(self):
        """
        启动入口
        """
        pages = ceil(self.total_addresses/12)
        for i in range(1, pages+1):
            timestamp = int(time.time()*1000)
            url = self.base_api.format(i, timestamp)
            self.tast_one(url, i)
            time.sleep(10)
        self.csvfile.close()

