import requests
import logging
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from retry import retry
from lxml.etree import HTML
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Get Url')

class Coingecko:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.dextools_jobs = 'project_review_en_version:dextools:jobs'

    @retry(tries=3, delay=3)
    def req(self, url):
        # User-Agent user-agent 这两种模式不兼容
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {url}')
        return res

    def get_contracts_address(self, url):
        """
        获取合约地址
        return: None or string
        """
        res = self.req(url)
        tree = HTML(res.text)
        pattern = '//span[text()="Contract"]/following-sibling::div/div[1]/div/i/@data-address'
        address_list = tree.xpath(pattern)
        if address_list:
            return address_list[0]
        return

    def run(self, url):
        """
        从HTML中解析出合约地址，并且将合约地址提交到dextools的任务队列
        # 解析出的合约地址一般为小写
        """
        contracts_address = self.get_contracts_address(url)
        if contracts_address:
            self.redis_cli.sadd(self.dextools_jobs,contracts_address)