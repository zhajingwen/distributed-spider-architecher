# -*- coding: utf-8 -*-
# from scrapy.crawler import logger
import logging
from utils.redisdb import redis_cli
from utils.db_utils import DataUtils
# from config import config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Pipeline Rds')

class MysqlPipeline:
    # 获取生产者client
    def __init__(self):
        self.redis_cli = redis_cli()
        self.headers = {"content-type": "application/json; charset=utf-8"}
        self.db = DataUtils('spider')

    def process_item(self, item, spider):
        # 不转化成dict kafka会推送失败
        item = dict(item)
        # # 去重
        # if self.filter(spider,item):
        #     return item
        sql = item['sql']
        if isinstance(sql,list):
            for s in sql:
                self.db.insert(s)
                logger.info(f'mysql pushed  successfully')
                # # 推送成功再写进去
                # self.redis_cli.sadd(f'{spider.name}:itemsfilter',id)
        else:
            self.db.insert(sql)
            logger.info(f'mysql pushed  successfully')
            # 推送成功再写进去
            id = item.get('id')
            if id:
                self.redis_cli.sadd(f'{spider.name}:itemsfilter',id)
        return item

    def filter(self, spider, item):
        """
        去重
        :param spider:
        :param item:
        :return:存在了就 过滤 返回True
        """
        # 指定爬虫不去重
        filter_exsits = hasattr(spider,'filter')
        if filter_exsits:
            if not spider.filter:
                # 爬虫不去重
                return False
        # item通过md5去重  是否存在该id
        status = self.redis_cli.sismember(f'{spider.name}:itemsfilter',item['id'])
        if status:
            return True
        else:
            return False

