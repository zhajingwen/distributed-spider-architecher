import os
import schedule
import time
import logging
from utils.rds import DataUtils
from datetime import datetime,date,timedelta
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Twitter Kol')

class Kol:
    def __init__(self):
        self.rds = DataUtils('spider')
        self.web_hook_api = os.getenv('LARK_WEBHOOK_FEISHU_ALERT', '')


    def alert(self):
        spider_date = datetime.now().strftime("%Y-%m-%d")
        yesterday = date.today() + timedelta(-1)
        spider_date_yesterday = yesterday.strftime("%Y-%m-%d")
        # sql_now = f"SELECT distinct coin_name,token_count FROM twitterscan_kol where spider_date={repr(spider_date)} order by token_count desc limit 20;"
        sql_now = f"SELECT distinct coin_name,token_count FROM twitterscan_kol WHERE spider_date={repr(spider_date)};"
        now_result = self.rds.select(sql_now)
        now_data = {}
        for item in now_result:
            coin_name = item["coin_name"]
            if coin_name in now_data:
                now_data[coin_name] += int(item['token_count'])

            else:
                now_data[coin_name] = int(item["token_count"])
        sql_yesterday = f"SELECT distinct coin_name,token_count FROM twitterscan_kol WHERE spider_date={repr(spider_date_yesterday)};"
        yesterday_result = self.rds.select(sql_yesterday)
        yesterday_data = {}
        for item in yesterday_result:
            coin_name = item["coin_name"]
            if coin_name in yesterday_data:
                yesterday_data[coin_name] += int(item['token_count'])

            else:
                yesterday_data[coin_name] = int(item["token_count"])
        diff_indexes = {}
        for key in now_data:
            if key in yesterday_data:
                if now_data[key] > 15:
                    diff_index = ((now_data[key] - yesterday_data[key])/yesterday_data[key])*100
                    diff_index = round(diff_index,3)
                    if diff_index > 0:
                        diff_indexes[f'{key}_{now_data[key]}_{yesterday_data[key]}'] = diff_index
        diff_indexes = sorted(diff_indexes.items(), key=lambda x: x[1])
        diff_indexes = list(reversed(diff_indexes))
        content = ''
        for item_tuple in diff_indexes:
            row = f'{item_tuple[0]}  热度涨幅：{item_tuple[1]}\n'
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
            logger.info('monitoring')


