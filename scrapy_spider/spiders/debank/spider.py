# -*- coding: utf-8 -*-
import os
import json
# from base64 import b64decode
# from datetime import datetime
# from urllib.parse import parse_qsl
from scrapy_redis.spiders import RedisSpider
from scrapy import FormRequest
from collections.abc import Iterable
from utils.redisdb import redis_cli


def gen_urls():
    """写入redis开始请求的队列"""
    name = 'debank'
    redis_key = f"{name}:start_url"
    # base_url = 'https://api.debank.com/user?id=0x310f3030e7cc99d9093c5fcd7e8a7fe4cc92b9d9'
    base_url = 'https://api.debank.com/user?id={}'

    addresses = []
    with open('scrapy_spider/spiders/debank/origin')as f:
        rows = f.read().strip().split('\n')
        for row in rows:
            addresses.append(row.strip())
    redis_c = redis_cli()
    with redis_c.pipeline(transaction=False) as p:
        for address in addresses:
            data = {
                'url': base_url.format(address),
                'meta': {
                    'Address': address,
                }
            }
            data = json.dumps(data)
            p.lpush(redis_key, data)
        p.execute()

    print('所有任务写入完成！')

class Spider(RedisSpider):
    # gen_urls()
    name = 'debank'
    redis_key = f"{name}:start_url"
    change_ua = True
    proxy = os.getenv('PROXY_URL', '')
    start_urls = []
    # 特殊pipeline
    custom_settings = {
        'ITEM_PIPELINES': {
            "scrapy_spider.ext_pipelines.rds_onchain_data_misc.MysqlPipeline": 100,
        }
    }

    def make_request_from_data(self, data):
        parameter = json.loads(data)
        url = parameter.pop("url")
        method = parameter.pop("method").upper() if "method" in parameter else "GET"
        metadata = parameter.pop("meta") if "meta" in parameter else {}
        address = metadata['Address']
        if self.server.sismember(f'{self.name}:itemsfilter', address):
            self.logger.info(f'已入库，过滤该请求：{address}')
            return
        return FormRequest(url, dont_filter=False, method=method, formdata=parameter, meta=metadata)

    def start_requests(self):
        found = 0
        datas = self.fetch_data(self.redis_key, self.redis_batch_size)
        for data in datas:
            reqs = self.make_request_from_data(data)
            # 过滤请求过拿到数据的
            if not reqs:
                continue
            if isinstance(reqs, Iterable):
                for req in reqs:
                    yield req
                    found += 1
                    self.logger.info(f'start req url:{req.url}')
            elif reqs:
                yield reqs
                found += 1
            else:
                self.logger.debug(f"Request not made from data: {data}")
        if found:
            self.logger.debug(f"Read {found} requests from '{self.redis_key}'")

    def parse(self, response, **kwargs):
        Address = response.meta['Address']
        data = json.loads(response.body)
        # 2608.2410599894465
        usd_value = data["data"]["user"]["desc"]["usd_value"]
        Balance = round(usd_value,2)
        sql = f"replace into debank values ({repr(Address)},{Balance},now());"
        result = {
            'sql': sql,
            'id': Address,
        }
        yield result
