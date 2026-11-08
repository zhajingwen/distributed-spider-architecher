# -*- coding: utf-8 -*-
import os
from scrapy_redis.spiders import RedisSpider
from scrapy.http import Request
import json


class Galxe(RedisSpider):
    # 翻页到一定程度就不吐数据了
    name = 'galxe'
    redis_key = f"{name}:start_url"
    change_ua = False
    # schedule_time = 12 * 5
    url = 'https://spidertools.cn/#/'
    start_urls = [url]
    headers = {
        "Authorization": os.getenv('AUTHORIZATION_GALXE', ''),
        "Content-Type": "application/json",
        "Origin": "https://galxe.com",
        'Referer':'https://galxe.com/Linea/leaderboard',
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    api = 'https://graphigo.prd.galaxy.eco/query'
    custom_settings = {
        'DOWNLOAD_DELAY': 100,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
    }
    first = 1000

    def parse(self, response, **kwargs):
        """
        发起列表页请求
        """
        self.logger.info(f'Parse: {response.url}')
        data = {
            "operationName": "SpaceLeaderboard",
            "variables": {
                "id": "20327",
                "first": self.first,
                "after": "-1",
                "order": "Points",
                "seasonId": None
            },
            "query": "query SpaceLeaderboard($id: Int!, $first: Int, $after: String, $order: LoyaltyPointsRankOrder, $seasonId: Int) {\n  space(id: $id) {\n    id\n    name\n    loyaltyPointsRanks(first: $first, after: $after, order: $order, sprintId: $seasonId) {\n      pageInfo {\n        startCursor\n        endCursor\n        hasNextPage\n        hasPreviousPage\n        __typename\n      }\n      totalCount\n      list {\n        id\n        rank\n        points\n        space {\n          name\n          __typename\n        }\n        address {\n          username\n          id\n          avatar\n          address\n          solanaAddress\n          aptosAddress\n          seiAddress\n          twitterUserName\n          discordUserName\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
        }
        body = json.dumps(data)
        yield Request(
            url=self.api,
            method='POST',
            headers=self.headers,
            body=body,
            meta={
                'page':1
            },
            dont_filter=True,
            callback=self.parse_list
        )
        self.logger.info(f'发起列表页请求：1 页')

    def parse_list(self, response):
        """
        解析结果和翻页
        """
        last_page = response.meta['page']
        self.logger.info(f'解析列表页：{last_page} 页')
        # 翻到后面就没有了
        data = json.loads(response.body)
        if 'errors' in data:
            self.logger.info(f'已经采集完，共 {last_page-1} 页')
            return

        ranks_list = data['data']['space']['loyaltyPointsRanks']['list']
        for index,r in enumerate(ranks_list):
            id = r['id']
            rank = (index+1) + (last_page-1)*self.first
            points = r['points']
            address = r['address']['address']
            discordUserName = r['address']['discordUserName']
            twitterUserName = r['address']['twitterUserName']
            if twitterUserName:
                twitter_url = f'https://twitter.com/{twitterUserName}'
            else:
                twitter_url = ''
            username = r['address']['username']
            sql = f'replace into galxe values({repr(id)},{rank},{points},{repr(address)},{repr(discordUserName)},{repr(twitter_url)},{repr(username)},now());'
            item = {
                'id':id,
                'sql':sql
            }
            yield item

        # 翻页
        after = last_page * self.first - 1
        data = {
            "operationName": "SpaceLeaderboard",
            "variables": {
                "id": "20327",
                "first": self.first,
                "after": f"{after}",
                "order": "Points",
                "seasonId": None
            },
            "query": "query SpaceLeaderboard($id: Int!, $first: Int, $after: String, $order: LoyaltyPointsRankOrder, $seasonId: Int) {\n  space(id: $id) {\n    id\n    name\n    loyaltyPointsRanks(first: $first, after: $after, order: $order, sprintId: $seasonId) {\n      pageInfo {\n        startCursor\n        endCursor\n        hasNextPage\n        hasPreviousPage\n        __typename\n      }\n      totalCount\n      list {\n        id\n        rank\n        points\n        space {\n          name\n          __typename\n        }\n        address {\n          username\n          id\n          avatar\n          address\n          solanaAddress\n          aptosAddress\n          seiAddress\n          twitterUserName\n          discordUserName\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
        }
        body = json.dumps(data)
        yield Request(
            url=self.api,
            method='POST',
            headers=self.headers,
            body=body,
            meta={
                'page':last_page+1
            },
            dont_filter=True,
            callback=self.parse_list
        )
        self.logger.info(f'发起列表页请求：{last_page+1} 页')