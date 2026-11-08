import requests
import time
import json
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
        self.cookies_store = 'coingecko:cookies'

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
                logger.info(f'该cookies已失效,抛弃，准备获取下一个：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry(tries=6, delay=3)
    def req(self, url):
        """
        发起请求
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        # 以下三项均来自rpc
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        headers = {
            "Referer": "https://www.coingecko.com/en/coins/marblex",
            'User-Agent': cookie_dict['ua']
        }
        # 发起get请求
        logger.info(f'Get {url}')
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            res = requests.get(url, headers=headers, proxies=proxies, cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies)
        logger.info(f'response code: {res.status_code} {url}')
        logger.info(f'request headers {res.request.headers}')
        if res.status_code != 200:
            error_content = f"url: {url} headers: {headers} proxies: {proxies} cookies: {cookie_dict}"
            logger.error(error_content)
            raise Exception(f'请求异常 response code {res.status_code}，切换IP重试...')
        # response 200 再把cookie放回去
        self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res


    # @retry(tries=3, delay=3)
    # def req(self, url):
    #     # User-Agent user-agent 这两种模式不兼容
    #     headers = {
    #         "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    #     }
    #     res = requests.get(url, headers=headers, proxies=proxies)
    #     if res.status_code != 200:
    #         raise Exception(f'响应码异常：{res.status_code} {url}')
    #     return res

    def get_contracts_address(self, url):
        """
        获取合约地址
        return: None or string
        """
        res = self.req(url)
        tree = HTML(res.text)
        pattern = '//*/@data-address'
        address_list = tree.xpath(pattern)
        if address_list:
            return address_list[0]
        else:
            logger.error('无法解析出合约地址')
        return

    def run(self, url):
        """
        从HTML中解析出合约地址，并且将合约地址提交到dextools的任务队列
        # 解析出的合约地址一般为小写
        """
        contracts_address = self.get_contracts_address(url)
        if contracts_address:
            self.redis_cli.sadd(self.dextools_jobs,contracts_address)