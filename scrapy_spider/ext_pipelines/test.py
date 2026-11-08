# -*- coding: utf-8 -*-
import logging
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('pipeline')

class Test:
    # 获取生产者client
    def __init__(self):
        self.redis_cli = redis_cli()

    def process_item(self, item, spider):
        # 不转化成dict kafka会推送失败
        item = dict(item)
        # print(item)
        # logger.info(f'mysql pushed {item} successfully')
        logger.info(item['id'])
        # print(f'type: {type(spider.name)}')
        # print(spider.name)
        # 推送成功再写进去
        # self.redis_cli.sadd(f'{spider.name}:itemsfilter',json.dumps(item))
        return item
