import os
import requests
import logging
import time
from datetime import datetime
from fake_useragent import UserAgent
from retry import retry
from utils.lark_bot import sender
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Whales Spider')


class Whales:
    def __init__(self):
        self.ua = UserAgent()
        self.api = 'https://api.whales.market/admins/token-info?take=100&category=pre_market'
        self.lark_webhook = os.getenv('LARK_WEBHOOK_PRE_MARKET_ALERT', '')
        self.redis_cli = redis_cli()
        self.filter_key_redis = 'whalesmarket:filter'

    @retry(tries=4, delay=4)
    def req(self):
        ua = self.ua.random
        headers = {
            "User-Agent": ua
        }
        logger.info(f'GET: {self.api}')
        # res = requests.get(self.api, headers=headers)
        res = requests.get(self.api, headers=headers, proxies=proxies)
        logger.info(f'Response: {res.status_code}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res

    def time_transform(self, timestamp):
        """
        将时间戳转换为日期
        """
        if timestamp:
            date = datetime.fromtimestamp(timestamp)
            date_str = date.strftime('%Y-%m-%d %H:%M')
            return date_str
        else:
            return '暂无'

    def get_tokens(self):
        res = self.req()
        data = res.json()
        data = data['data']
        for item in data:
            symbol = item['symbol']
            start_time = item['start_time']
            start_time = self.time_transform(start_time)
            id = item['id']
            twitter = item['twitter']
            website = item['website']
            content = f"""
            symbol: {symbol}
            start_time: {start_time}
            twitter: {twitter}
            website: {website}
            """
            alerted_status = self.redis_cli.sismember(self.filter_key_redis, id)
            # 判断是否已经高经过
            if not alerted_status:
                sender(content, self.lark_webhook, '新项目上线')
                # 告警过的记录redis
                self.redis_cli.sadd(self.filter_key_redis, id)

    def run(self):
        """
        启动入口
        """
        while True:
            self.get_tokens()
            # 每小时调度一次
            time.sleep(60*60)