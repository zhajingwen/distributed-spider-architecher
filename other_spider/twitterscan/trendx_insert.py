import json
import requests
import time
import os
import logging
from hashlib import md5
from datetime import datetime,date, timedelta
from utils.rds import DataUtils
from traceback import format_exc
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Trendx')
env = os.environ.get('env')

class TrendxInsert:
    def __init__(self):
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        # get请求，无鉴权，热度值排序
        # 前100条数据
        self.url = 'https://app.trendx.tech/v1/dao/public/projects/stars?sort=heat1&order=2&page=1&rows=100'
        self.lark_webhook = os.getenv('LARK_WEBHOOK_TWITTERSCAN', '')
        self.table = 'trendx'
        self.rds = DataUtils('spider')

    @retry(tries=6, delay=3)
    def req_trending(self):
        """
        发起trending tokens 请求
        """
        logger.info(f'GET: {self.url}')
        if env == 'local':
            res = requests.get(self.url, headers=self.headers)
        else:
            res = requests.get(self.url, headers=self.headers, proxies=proxies)
        try:
            self.parse_trending(res)
        except:
            logger.error(format_exc())
            logger.error('trending解析异常')
        logger.info(f'response {res.status_code}: {self.url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常 {res.status_code}')

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

    def parse_trending(self, response):
        """
        解析trending tokens
        """
        data = response.json()
        rows = data['data']['rows']
        all_update_sql_base = "REPLACE INTO {} values{};"
        sql_values = []

        for index, item in enumerate(rows):
            image = json.loads(item['image'])
            name = item['fullName']
            spider_date = datetime.now().strftime('%Y-%m-%d')
            id = md5(f'{name}{spider_date}'.encode('utf-8')).hexdigest()
            symbol = item.get('tokenSymbol','')
            type_ = item.get('category', '')
            chain = item['chain']
            heat = item['heat1']
            vote = item['voteTotal']
            vote_agree_percent = int((item['passCount']/vote)*100)
            vote_agree_percent = f'{vote_agree_percent}%'
            vote = self.num_transform(vote)
            sentiment = round(item['sentimentIndex1'], 2)
            twitterFollowers = item['twitterFollowers']
            twitterFollowers = self.num_transform(twitterFollowers)
            dissussion_count = item['discussions1']
            kol_whale = item['kolWhales']
            if kol_whale == None:
                kol_whale = 'null'
            price = item.get('currencyPrice','null')
            if price == None:
                price = 'null'
            logger.info(image)
            logo = image.get('logoUrl', 'null')
            sql = f'({repr(id)},{repr(name)},{repr(symbol)},{repr(type_)},{repr(chain)},' \
                  f'{heat},{repr(vote)},{repr(vote_agree_percent)},{sentiment},{repr(twitterFollowers)},' \
                  f'{dissussion_count},{kol_whale},{price},{repr(spider_date)},{repr(logo)})'
            sql_values.append(sql)
        sqls = ','.join(sql_values)
        combine_sql = all_update_sql_base.format(self.table, sqls)
        self.rds.insert(combine_sql)

    def run(self):
        """
        启动入口 定时调度
        """
        if env != 'prod':
            self.req_trending()
        else:
            logger.info(f'程序启动，等待调度中...')
            while True:
                # 每日6：00 - 8：10为可执行时间区间，拉长可执行时间可以避免容器异常时恰好卡在了调度时间区间内，导致无法正常调度
                today_now = datetime.now()
                today_at_06_00 = today_now.replace(hour=6, minute=0, second=0)
                today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
                if today_at_06_00 < today_now < today_at_08_10:
                    logger.info('激活调度')
                    self.req_trending()
                    logger.info('调度结束')
                    time.sleep(2*60*60)
                time.sleep(10)