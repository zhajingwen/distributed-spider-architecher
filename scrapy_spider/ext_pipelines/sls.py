# -*- coding: utf-8 -*-
import json
import time
import os
import json
import sys
from aliyun.log import *
from traceback import print_exc
from utils.redisdb import redis_cli
from config import config
from scrapy.crawler import logger
from utils.redisdb import redis_cli
from utils.db_utils import DataUtils
from config import config
# import logging
#
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger('SPIDER')
# sys.path.append('./')

env = os.environ.get('env')

class Sls:

    def __init__(self):
        endpoint = config.ENDPOINT
        accessKeyId = config.ACCESSKEYID
        accessKey = config.ACCESSKEY
        self.project = config.PROJECT
        self.sls_client = LogClient(endpoint, accessKeyId, accessKey)

    def push_to_sls(self, data, logstore):
        # 测试环境的sls项目
        project = self.project
        logitemList = []  # LogItem list
        # 批量插入 sls 列表嵌套列表
        # for data in data_list:
        # 为了兼容ins
        user = data.get('user')
        body = json.dumps(data)
        if user:
            contents = [
                ('result', body),
                ('user',user)
            ]
        else:
            # 是否需要将json打散
            if data.get('friable'):
                contents = list(data.items())
            else:
                contents = [
                    ('result', body)
                ]
        logItem = LogItem()
        logItem.set_time(int(time.time()))
        logItem.set_contents(contents)
        logitemList.append(logItem)
        request = PutLogsRequest(project, logstore, logitems=logitemList)
        response = self.sls_client.put_logs(request)
        response.log_print()

    def pipline(self, item, logstore='md-amazon-keyword-search'):
        """
        result_list：结果列表，代表每页的数据，考量到下游消费能够同步进行，不是把所有的搜索结果放入一个列表中
        result数据样例见191行代码
        """
        # 判断是否有数据
        # 写入redis
        # if not result_list:
        #     return
        num = 0
        # sls 落库可能会失败
        while True:
            try:
                self.push_to_sls(item,logstore)
                break
            except:
                print_exc()
                logger.error(f'item: {item}')
                num += 1
                logger.error(f'sls落入失败，重试{num}')
                time.sleep(1)

    def process_item(self, item, spider):
        # 不转化成dict kafka会推送失败
        item = dict(item)
        logstore = spider.logstore
        if logstore:
            self.pipline(item,logstore)
            return item
        else:
            logger.error('没有定义logstore')
