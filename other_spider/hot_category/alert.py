import os
import time
import logging
from .spider import Spider
from .data_increased import Increased
from utils.lark_bot import sender
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Hot Category')
env = os.environ.get('env')

class AlertEntrance:
    def __init__(self):
        self.spider = Spider()
        self.history = Increased()
        self.web_hook = os.getenv('LARK_WEBHOOK_HOT_CATEGORY_2', '')

    def task(self):
        """
        任务
        """
        categories_marketcap,categories_volume24h = self.spider.calculate_categories_marketcap()
        content_tuple = self.history.alert_content()
        content_json = content_tuple[0]
        alert_content = ''
        for category in content_json:
            c_alert_content = content_json[category]
            row_content = f'{category}：{c_alert_content}\n'
            alert_content += row_content
        sender(alert_content, self.web_hook, '暴涨板块')
        # 板块涨幅排行
        content_sorted = content_tuple[1]
        sender(content_sorted, self.web_hook, '板块涨幅排行')

    def scheduler(self):
        """
        定时调度
        """
        while True:
            # 每日08：10分执行
            today_now = datetime.now()
            today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
            today_at_08_11  = today_now.replace(hour=8, minute=11, second=0)
            if env == 'prod':
                if today_at_08_10 < today_now < today_at_08_11:
                    self.task()
                    logger.info('调度结束')
                    time.sleep(60*60)
            else:
                self.task()
                logger.info('一次性任务结束')
                break
            time.sleep(10)

    def run(self):
        logger.info('启动定时调度任务，每日一次，每日8:10')
        self.scheduler()

