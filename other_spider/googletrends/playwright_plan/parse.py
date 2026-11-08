import os
import logging
from hashlib import md5
from utils.rds import DataUtils
from .worldwide import insert_data_worldwide
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GOOGLE TRENDS Parse')

class ParseData:
    def __init__(self):
        self.rds = DataUtils('spider')
        self.table = 'google_trends2'
        self.lark_api = os.getenv('LARK_WEBHOOK_GOOGLETRENDS', '')

    def parse_insert_to_db(self, data, country, spider_date, geo, area, spider_time):
        all_update_sql_base = "replace into {}(id,geo,country,area,related_words,spider_time,spider_date) values{};"
        sql_values = []
        if geo == '':
            status = insert_data_worldwide(data, spider_date, self.rds, spider_time)
            if not status:
                logger.info(f'worldwide 请求成功，但是数据为空 {data}')
                sender(f'无数据加载', self.lark_api, 'worldwide异常')
            return
        for d in data:
            related_words = d['query']
            # 存在一大段句子的情况
            if len(related_words) > 100:
                continue
            if len(related_words.split(' ')) > 5:
                continue
            id = md5(f'{country}{spider_date}{related_words}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(geo)},{repr(country)},{repr(area)},{repr(related_words)},{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
            if data.index(d) == 9:
                break
        if not data:
            logger.info(f'{geo} {spider_date} 请求成功，但是数据为空 {data}')
            id = md5(f'{country}{spider_time}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(geo)},{repr(country)},{repr(area)},'',{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
            self.rds.insert(all_update_sql)
