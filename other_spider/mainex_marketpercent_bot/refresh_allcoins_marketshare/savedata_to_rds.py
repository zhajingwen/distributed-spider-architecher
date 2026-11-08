import time
import logging
import os
from datetime import datetime
from .spiders.coingecko_marketpercent import Coingecko
from .spiders.cmc_marketpercent import CmcSpider
from other_spider.mainex_marketpercent_bot.refresh_allcoins_marketshare.filter_and_mapcmc import FilterMap
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Crontab Job Schedule Everyday Morning 8 Am')
env = os.environ.get('env')

class Job:

    def save_marketshare_info(self):
        """
        refresh once coinsadjust every morning
        """
        self.cmcspider = CmcSpider()
        self.coingecko = Coingecko()
        rds = DataUtils()
        # target coins
        jobs = FilterMap().map_job_tocmc()
        for job in jobs:
            logger.info(f'执行市占率入库任务：{job["name"]}')
            # get data from spider(cmc) and insert them to rds
            insert_status = self.cmcspider.crawl_data_and_insert_to_rds(job, rds)
            # can't find mainex in cmc marketing list
            if insert_status == False:
                logger.warning(f'CMC未收录：{job},从Coingecko获取数据...')
                self.coingecko.run(job, rds)
            else:
                logger.info(f'市占率数据入库成功：{job["name"]}')

    def schedule(self):
        """
        启动入口 定时调度
        """
        if env != 'prod':
            logger.info('任务立即执行')
            self.save_marketshare_info()
        else:
            logger.info(f'程序启动，等待调度中...')
            while True:
                today_now = datetime.now()
                today_at_08_00 = today_now.replace(hour=8, minute=0, second=0)
                today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
                if today_at_08_00 < today_now < today_at_08_10:
                    logger.info('激活调度')
                    self.save_marketshare_info()
                    logger.info('调度结束')
                    time.sleep(60 * 60)
                time.sleep(10)
