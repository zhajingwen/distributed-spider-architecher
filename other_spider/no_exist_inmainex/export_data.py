# import requests
import logging
import json
import csv
# import time
# from retry import retry
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Export Data To CSV')

class Export:
    """
    dextools爬虫
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.result_key = 'noexistinmainex:exporteddone5'
        file_name = 'nolisting inmainex.csv'
        self.csvfile = open(file_name, 'a', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.csvfile)
        self.done_key = 'noexistinmainex:exporteddone6'

    def run(self):
        """
        处理输入的消息是合约地址
        """
        # 已上线mainex的name list
        mainex_listing_names = []
        all_mainex_names = self.redis_cli.hgetall('mainex:idsnames')
        for key in all_mainex_names:
            value = all_mainex_names[key]
            logger.info(value)
            mainex_listing_names.append(value)



        title = None
        while True:
            job = self.redis_cli.spop(self.result_key)
            if not job:
                logger.info('任务已全部消费完')
                break
            if not isinstance(job, dict):
                job = json.loads(job)
            if title == None:
                if 'cex' in job:
                    keys = []
                    for key in job:
                        keys.append(key)
                    self.writer.writerow(keys)
                    title = True

            # 过滤数据
            if job.get('cex'):
                if 'Mainex' in job.get('cex'):
                    continue
            symbol = job['symbol']
            symbol = f'{symbol.upper()}/USDT'
            symbol_listing_status = self.redis_cli.hget('mainex:marketpairs', symbol)
            if symbol_listing_status:
                logger.warning(f'已上线mainex：{symbol}')
                continue
            name = job['name']
            if name in mainex_listing_names:
                logger.warning(f'已上线mainex：{name}')
                continue
            row_value_list = []
            for key in job:
                value = job[key]
                row_value_list.append(value)
            self.writer.writerow(row_value_list)
            # logger.info(f'写入：{row_value_list}')
            # 备份
            self.redis_cli.sadd(self.done_key, json.dumps(job))
        self.csvfile.close()