# -*- coding: utf-8 -*-
from scrapy.crawler import logger
from utils.redisdb import redis_cli
from config import config
from pymongo import MongoClient


class MongodbPipeline:
    # 获取生产者client
    def __init__(self):
        self.redis_cli = redis_cli()
        MONGODBCONF = config.MONGODBCONF
        mongo_client = MongoClient(MONGODBCONF)
        self.mongo_db = mongo_client['spider_data']

    def process_item(self, item, spider):
        item = dict(item)
        id = item['pop_id']
        while True:
            try:
                # upsert 不存在则新增，存在则更新
                self.mongo_db[spider.name].update({'_id': item['pop_id']}, {'$set': item},upsert=True)
                break
            except:
                logger.info('mongodb链接断掉，重新连接')
                MONGODBCONF = config.MONGODBCONF
                mongo_client = MongoClient(MONGODBCONF)
                self.mongo_db = mongo_client['spider_data']
        logger.info(f'mongodb pushed {id} successfully')
        # 推送成功再写进去
        self.redis_cli.sadd(f'{spider.name}:itemsfilter',id)
        return item

    def filter(self,spider,item):
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
        status = self.redis_cli.sismember(f'{spider.name}:itemsfilter',item['pop_id'])
        if status:
            return True
        else:
            return False

