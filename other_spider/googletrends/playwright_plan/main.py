import schedule
import time
import os
import logging
from datetime import datetime
from .playwright_run import Play
from .config import countrys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GoogleTrendsMain')
env = os.environ.get('env')

class SearchRelation:
    def __init__(self, browser_type):
        self.countrys = countrys
        self.headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        self.browser_type = browser_type

    def req(self, country="美国", spider_time=1111, spider_date='None'):
        """
        调用playwright hook数据
        """
        geo = self.countrys[country]['geo']
        area = self.countrys[country]['area']
        data = {
            'country':country,
            'spider_date': spider_date,
            'geo': geo,
            'area': area,
            'spider_time': spider_time,
        }
        url = f'https://trends.google.com/trends/explore?q=crypto&date=now%201-d&geo={geo}&hl=en-US&tz=360'
        if not geo:
            url = 'https://trends.google.com/trends/explore?q=crypto&date=now%201-d&hl=en-US&tz=360'
        Play().run(url, data, self.browser_type)

    def all_country(self):
        """
        采集所有国家
        """
        spider_time = int(time.time())
        spider_date = datetime.now().strftime("%Y-%m-%d")
        for country_name in self.countrys:
            logger.info(f'开始采集：{country_name} {spider_date}')
            self.req(country_name, spider_time, spider_date)

    def run(self):
        """
        启动入口 定时调度
        """
        if env != 'prod':
            self.all_country()
        else:
            logger.info(f'程序启动，等待调度中...')
            while True:
                # 每日6：00 - 8：10为可执行时间区间，拉长可执行时间可以避免容器异常时恰好卡在了调度时间区间内，导致无法正常调度
                today_now = datetime.now()
                today_at_06_00 = today_now.replace(hour=6, minute=0, second=0)
                today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
                if today_at_06_00 < today_now < today_at_08_10:
                    logger.info('激活调度')
                    self.all_country()
                    logger.info('调度结束')
                    time.sleep(60 * 60)
                time.sleep(10)
