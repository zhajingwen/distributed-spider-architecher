import os
import schedule
import time
from utils.rds import DataUtils
from datetime import datetime
from other_spider.cmc.bot.lark_bot import sender


class Kol:
    def __init__(self):
        self.rds = DataUtils('spider')
        self.web_hook_api = os.getenv('LARK_WEBHOOK_FEISHU_ALERT', '')


    def alert(self):
        spider_date = datetime.now().strftime("%Y-%m-%d")
        sql = f"SELECT distinct coin_name,token_count FROM twitterscan_kol where spider_date={repr(spider_date)} order by token_count desc limit 20;"
        result = self.rds.select(sql)
        content = ''
        for item in result:
            row = f'{item["coin_name"]}  热度值：{item["token_count"]}\n'
            content += row
        sender(content,self.web_hook_api,'kol hot coin')

    def run(self):
        """
        启动入口 定时调度
        """
        # 每天9：30 启动
        schedule.every().day.at("09:30").do(self.alert)
        while True:
            schedule.run_pending()
            time.sleep(1)

