from curl_cffi import requests
import logging
import time
# import stweet as st
import json
# from traceback import format_exc
from retry import retry
from .twitter_spider import Spider as TSpider
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BK Spider')


class Spider:
    def __init__(self):
        # self.dextools_url1 = 'https://www.dextools.io/shared/data/pair?address=0xa43fe16908251ee70ef74718545e4fe6c5ccec9f&chain=ether&audit=true'
        self.detail_url = 'https://www.dextools.io/shared/data/pair?address={}&chain={}'
        self.search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        # self.headers = {
        # }
        self.tspider = TSpider()
        self.cookies_store = 'bk-early:cookies'
        self.redis_cli = redis_cli()

    # def req(self, url):
    #     """
    #     发起请求
    #     """
    #     res = requests.get(url, headers=self.headers)
    #     logger.info(f'{res.status_code} {url}')
    #     if res.status_code != 200:
    #         logger.warning('响应码错误！')
    #         return
    #     return res

    # def get_cap_liquidity(self, url):
    #     res = self.req(url)
    #     logger.info(res.text)
    #     data = res.json()['data'][0]
    #     # 有可能是null
    #     mcap = data['token']['metrics'].get('mcap')
    #     liquidity = data['metrics']['liquidity']
    #     volume24 = data['price24h']['volume']
    #     price = data['price']
    #     totalSupply = data['token']['metrics']['totalSupply']
    #
    #     if not mcap:
    #         mcap = price*totalSupply
    #     return mcap, liquidity,volume24

    def twitter_user_info(self, twitter_id):
        """
        获取twitter粉丝量
        """
        if not twitter_id:
            return '无twitter账户'
        # user_task = st.GetUsersTask([twitter_id])
        # output_print = st.PrintRawOutput()
        logger.info(f'开始采集twitter: {twitter_id}')
        # res = st.GetUsersRunner(get_user_task=user_task, raw_data_outputs=[output_print]).run()
        # if isinstance(res,list):
        #     user_content = res[1][0][0]
        # elif isinstance(res,tuple):
        #     user_content = res[1][0][0]
        # elif isinstance(res,dict):
        #     user_content = res
        # else:
        #     user_content = res[1][0][0]
        # if user_content:
        #     if isinstance(user_content,str):
        #         user_content = json.loads(user_content)
        #     followers_count = user_content['raw_value']['legacy']['followers_count']
        followers_count = self.tspider.run(twitter_id)
        return followers_count

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

    @retry(tries=6, delay=3)
    def req(self, keyword):
        """
        发起请求
        """
        url = self.search_url.format(keyword.strip())
        # 获取cookie
        cookie_dict = self.get_cookie()
        # 以下三项均来自rpc
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        headers = {
            "Referer": "https://www.dextools.io/app/cn/pairs",
            'User-Agent': cookie_dict['ua']
        }
        # 发起get请求
        logger.info(f'Get {url}')
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101", cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101")
        logger.info(f'response code: {res.status_code} {url}')
        logger.info(f'request headers {res.request.headers}')
        if res.status_code != 200:
            error_content = f"url: {url} headers: {headers} proxies: {proxies} cookies: {cookie_dict['cf']}"
            logger.error(error_content)
            raise Exception(f'请求异常 response code {res.status_code}，切换IP重试...')
        else:
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def search(self, keyword):
        """
        搜索币
        """
        # 发起请求
        res = self.req(keyword)
        data = res.json()['results'][0]
        pair = data['id']['pair']
        chain = data['id']['chain']
        token = data['id']['token']
        symbol = data['symbol']
        # 很多情况无 Twitter
        try:
            twitter = data['token']['links']['twitter']
            twitter_id = twitter.split('/')[-1]
        except:
            logger.warning(f'无 Twitter: {keyword}')
            twitter_id = None
        # detail_url = self.detail_url.format(pair,chain)
        # mcap,liquidity,volume24 = self.get_cap_liquidity(detail_url)

        # 有可能是null
        mcap = data['token']['metrics'].get('mcap')
        liquidity = data['metrics']['liquidity']
        volume24 = data.get('volume')
        if volume24:
            volume24 = int(volume24)
        price = data['price']
        totalSupply = data['token']['metrics']['totalSupply']
        if not mcap:
            mcap = price*totalSupply
        if twitter_id:
            twitter_followers = self.twitter_user_info(twitter_id)
        else:
            twitter_followers = '无Twitter'
        content = f"""代币简称：{symbol}
        总流动性：{int(liquidity)}
        24小时容量：{volume24}
        市场总量：{int(mcap)}
        Token 合约：{token}
        twitter粉丝量：{twitter_followers}"""
        logger.info(content)
        return content