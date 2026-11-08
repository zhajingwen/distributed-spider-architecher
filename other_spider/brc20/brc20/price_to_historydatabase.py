import time
import json
import logging
from utils.rds import DataUtils
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 Newest Price To History')


class Spider:
    def __init__(self):
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.price_update_timelimitjob = 'crawl-brc20:price:update_timelimtjob'

    def history_prices(self, jobs):
        """
        最新价格数据写入历史价格数据库
        """
        sql_base = "replace into brc20_token_price (token_name,price,price_date) values {};"
        sql_list = []
        for job in jobs:
            job = json.loads(job)
            name = job['name']
            price = job['price']
            price_date = job['time_stamp']
            sql_one = f'({repr(name)},{repr(price)},{price_date})'
            sql_list.append(sql_one)
        if sql_list:
            sqls = sql_base.format(','.join(sql_list))
            status = self.rds.insert(sqls)
            if status:
                logger.info(f'成功刷入价格到历史价格表，{len(sql_list)} 条')

    def consumer(self):
        """
        从redis消费任务
        """
        jobs = []
        while True:
            job = self.redis_cli.spop(self.price_update_timelimitjob)
            if job:
                jobs.append(job)
            else:
                break
        if not jobs:
            logger.info('当前无任务')
            time.sleep(30)
            return
        self.history_prices(jobs)
        # 每10s批量刷一次
        time.sleep(10)

    def run(self):
        while True:
            self.consumer()


if __name__ == '__main__':
    Spider().run()
