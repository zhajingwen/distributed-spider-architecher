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
        self.api = 'https://api-v2.whales.market/v2/tokens?take=50&page=1&category=pre_market&statuses[]=draft&statuses[]=active'
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

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
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

    def get_tokens(self):
        res = self.req()
        data = res.json()
        data = data['data']['list']
        for item in data:
            status = item['status']
            if status == 'draft':
                status = '尚未开放交易'
            else:
                status = '已开放交易'
            name = item['name']
            symbol = item['symbol']
            network_name = item['network_name']
            start_time = item['start_time']
            start_time = self.time_transform(start_time)
            id = item['id']
            twitter = item['twitter']
            website = item['website']
            last_price = item['last_price']
            volume_h24 = item['volume']['h24']
            volume_h24 = self.num_transform(int(volume_h24))
            volume_change_h24 = item['volume_change']['h24']
            volume_change_h24 = round(volume_change_h24, 2)
            trade_url = f'https://pro.whales.market/pre/{network_name}/{symbol}'
            content = f"""
            name: {name}            
            symbol: {symbol}
            chain: {network_name} 
            listing status: {status}                        
            price: {last_price}    
            volume 24h: {volume_h24}     
            volume change 24h: {volume_change_h24}     
            start_time: {start_time}
            twitter: {twitter}
            website: {website}
            trade: {trade_url}
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
            try:
                self.get_tokens()
            except:
                web_hook_api = os.getenv('LARK_WEBHOOK_ALERT', '')
                sender('程序挂了！', web_hook_api, 'Premarket whales market')
            # 每小时调度一次
            time.sleep(60*60)