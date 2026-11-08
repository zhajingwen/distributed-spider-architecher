# -*- coding: utf-8 -*-
from scrapy_redis.spiders import RedisSpider
from scrapy.http import Request
import json


class LineaScan(RedisSpider):
    # 翻页到一定程度就不吐数据了
    name = 'lineascan'
    redis_key = f"{name}:start_url"
    proxy = False
    url = 'https://lineascan.build/token/generic-tokentxns2?contractAddress=0x0872ec4426103482a50f26ffc32acefcec61b3c9&mode=&sid=f424ae9e81a79246a3efb7e2ced20b76&m=normal&p=176'
    url_base = 'https://lineascan.build/token/generic-tokentxns2?contractAddress=0x0872ec4426103482a50f26ffc32acefcec61b3c9&mode=&sid=f424ae9e81a79246a3efb7e2ced20b76&m=normal&p={}'

    custom_settings = {
        'DOWNLOAD_DELAY': 10,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    cookies = {
        'ASP.NET_SessionId': 'ejiw5rbvscrqmw32iwbxxo3k',
        '_ga': 'GA1.1.2022130609.1690189640',
        '_ga_7HXXHXN492': 'GS1.1.1690189640.1.1.1690189752.0.0.0',
        'LineaScan_cookieconsent': 'True',
    }

    def start_requests(self):
        # yield Request(
        #
        # )
        yield Request(
            url=self.url,
            # method='POST',
            headers=self.headers,
            # body=body,
            cookies=self.cookies,
            meta={
                'page': 176
            },
            dont_filter=True,
            # callback=self.parse_list
        )
        self.logger.info(f'发起列表页请求：{self.url}')

    def parse(self, response, **kwargs):
        """
        解析入库并发起列表页翻页请求
        """
        last_page = response.meta['page']
        patterns_from = response.xpath('//td[@class="showAge "]/following-sibling::td[1]')
        # print(patterns_from)
        sqls = []
        for p in patterns_from:
            res =p.xpath('.//a/text()').extract()[0]
            sql = f'replace into lineascan values({repr(res)},{repr(res)},now());'
            sqls.append(sql)
            # self.logger.info(res)
        patterns_to = response.xpath('//td[@class="showAge "]/following-sibling::td[3]')
        for p in patterns_to:
            res =p.xpath('.//a/text()').extract()[0]
            sql = f'replace into lineascan values({repr(res)},{repr(res)},now());'
            sqls.append(sql)
            # self.logger.info(res)
        yield {
            'sql':sqls
        }
        if last_page < 4000:
            yield Request(
            url=self.url_base.format(last_page+1),
            # method='POST',
            headers=self.headers,
            # body=body,
            # cookies=self.cookies,
            meta={
                'page': last_page+1
            },
            dont_filter=True,
            )
            self.logger.info(f'发起列表页请求：{self.url_base.format(last_page+1)}')

