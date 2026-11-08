import requests
import logging
import os
import time
from retry import retry
from datetime import datetime, timedelta
from threading import Thread
from utils.rds import DataUtils
from utils.proxy_requests import proxies
from utils.lark_bot import sender
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Geniidata BTC Gas')
env = os.environ.get('env')

class GasSpider:
    def __init__(self):
        self.gas_api = 'https://mempool.space/api/v1/fees/recommended'
        self.web_hook_api = os.getenv('LARK_WEBHOOK_BTC_GAS', '')
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.table_name = 'btc_gas'
        self.redis_cli = redis_cli()
        self.redis_gas_database = 'btc_gas:jsondata'

    @retry(tries=3, delay=6)
    def req(self, url):
        """
        发起请求拿数据
        """
        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        # res = requests.get(url, headers=self.headers)
        logger.info(f'Response: {res.status_code}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        return res

    def get_yesterday_gas(self):
        """
        获取昨日gas数据
        return: int or Bule
        """
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sql = f'select gas from {self.table_name} where spider_date={repr(yesterday_str)};'
        data = self.rds.select(sql)
        if data:
            data = data[0]
            old_gas = data['gas']
            return old_gas
        else:
            return False

    def now_gas(self):
        """
        拿到当前gas数据
        return: int
        """
        # 获取redis存的gas
        old_gas = self.redis_cli.hget(self.redis_gas_database, 'gas')
        old_times = self.redis_cli.hget(self.redis_gas_database, 'times')
        # 计算gas的平均值
        gas = int(int(old_gas)/int(old_times))
        # 重置统计容器（redis）
        self.redis_cli.hset(self.redis_gas_database, 'gas', 0)
        self.redis_cli.hset(self.redis_gas_database, 'times', 0)
        spider_date = datetime.now().strftime("%Y-%m-%d")
        sql = f'replace into {self.table_name} values({repr(spider_date)},{gas},{int(time.time())});'
        self.rds.insert(sql)
        return gas

    def refresh_gas_to_redis(self):
        """
        每小时刷新一次，将刷新的gas写入redis
        每次都在原有的数据上进行累计，累计gas总值和累计的次数
        """
        response = self.req(self.gas_api)
        data = response.json()
        halfHourFee = data['halfHourFee']
        old_gas = self.redis_cli.hget(self.redis_gas_database, 'gas')
        old_times = self.redis_cli.hget(self.redis_gas_database, 'times')
        if not old_gas:
            old_gas = 0
        if not old_times:
            old_times = 0
        old_gas = int(old_gas)
        old_times = int(old_times)
        # 刷新数据库
        self.redis_cli.hset(self.redis_gas_database, 'gas', old_gas+halfHourFee)
        self.redis_cli.hset(self.redis_gas_database, 'times', old_times+1)
        logger.info(f'redis已经刷新：{old_gas+halfHourFee} {old_times+1}')

    def calculate_job(self):
        """
        每小时累计一次gas值
        """
        while True:
            self.refresh_gas_to_redis()
            time.sleep(60*60)

    def refresh_rds_alert(self):
        """
        刷新rds内的数据，并且发出告警到告警频道
        """
        while True:
            # 可能存在数据库连接失败的问题，目前还不清楚为什么
            try:
                self.rds = DataUtils()
                now_gas = self.now_gas()
                yesterday_gas = self.get_yesterday_gas()
                gas_title = f'GAS: {now_gas}'
                if yesterday_gas:
                    increased_percent = round(((now_gas - yesterday_gas)/yesterday_gas)*100, 2)
                    content = f'同比昨日涨幅：{increased_percent}%'
                else:
                    content = '昨日无数据'
                sender(content, self.web_hook_api, gas_title)
                break
            except:
                logger.error(f'mysql连接失败，重试...')
                time.sleep(10)

    def alert_job(self):
        """
        执行告警任务
        """
        if env != 'prod':
            self.refresh_rds_alert()
        else:
            logger.info(f'程序启动，等待调度中...')
            while True:
                # 每日8：00 - 8：10为可执行时间区间
                today_now = datetime.now()
                today_at_08_00 = today_now.replace(hour=8, minute=0, second=0)
                today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
                if today_at_08_00 < today_now < today_at_08_10:
                    logger.info('激活调度')
                    self.refresh_rds_alert()
                    logger.info('调度结束')
                    time.sleep(60 * 60)
                time.sleep(10)

    def run(self):
        """
        启动入口 定时调度
        """
        # 计算gas平均值任务
        t = Thread(target=self.calculate_job)
        t.start()
        # 每日早晨的告警任务
        self.alert_job()

