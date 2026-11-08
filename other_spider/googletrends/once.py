import asyncio
import json
import os
import logging
import time
import csv
from playwright.async_api import async_playwright
# from traceback import format_exc
from threading import Thread
from functools import partial
# from .parse import ParseData
from utils.redisdb import redis_cli
from utils.lark_bot import sender


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GoogleTrends Playwright')
env = os.environ.get('env')

class Play:
    def __init__(self):
        self.check_key_base = 'googletrends:check:{}'
        self.redis_cli = redis_cli()
        self.web_hook = os.getenv('LARK_WEBHOOK_GOOGLETRENDS', '')

        topic_path = 'other_spider/googletrends/topic.csv'
        topic_file = open(topic_path, 'a', encoding='utf-8-sig', newline='')
        self.topic_writer = csv.writer(topic_file)

        queries_path = 'other_spider/googletrends/queries.csv'
        queries_file = open(queries_path, 'a', encoding='utf-8-sig', newline='')
        self.queries_writer = csv.writer(queries_file)
        self.success_list = []

    async def on_response(self, params, response):
        """
        hook数据
        """
        geo = params['geo']
        # 去重
        if f'{geo}-topics' in self.success_list and f'{geo}-query' in self.success_list:
            self.success_list.append(geo)
            return
        name = params['name']
        # 校验是否成功的redis key  如果失败这个key会存在
        # key = self.check_key_base.format(geo)
        if 'relatedsearches' in response.url:
            try:
                oridata = await response.text()
                data = oridata.strip().split('\n')[-1]
                data = json.loads(data)
                logger.info(f'捕获数据接口: {geo}')
            except:
                logger.error(f'数据拦截异常，未加载进来：{geo}')
                # logger.error(f'{format_exc()}')
                # self.redis_cli.set(key, 1)
                return
            data = data['default']['rankedList'][1]['rankedKeyword']
            # relatedsearches有两个接口，另外一个关联topic过滤
            if data:
                row_list = [name,'3m']
                if 'query' in data[0]:
                    logger.info('related queries')
                    for item in data:
                        keyword = item['query']
                        row_list.append(keyword)
                    self.queries_writer.writerow(row_list)
                    self.success_list.append(f'{geo}-query')
                    logger.info(f'csv 写入成功 {geo}-query')
                else:
                    logger.info('related topics')
                    for item in data:
                        topic = item['topic']
                        title = topic['title']
                        type = topic['type']
                        keyword = f'{title} - {type}'
                        row_list.append(keyword)
                    self.topic_writer.writerow(row_list)
                    self.success_list.append(f'{geo}-topics')
                    logger.info(f'csv 写入成功 {geo}-topics')
                # self.success_list.append(geo)

    async def lanch_chrome(self, url, data):
        """
        启动浏览器
        """
        # if env == 'local':
        launch_data = {
            "headless": False,
            "args": [
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-service-autorun",
                "--no-default-browser-check",
                "--password-store=basic",
            ],
        }
        async with async_playwright() as p:
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            # 实现传参给response
            response_handler = partial(self.on_response, data)
            page.on('response', response_handler)
            enable_url = 'https://trends.google.com'
            await page.goto(enable_url, timeout=0)
            await asyncio.sleep(3)
            await page.goto(url, timeout=0)
            geo = data['geo']
            num = 0
            while num < 10:
                num += 1
                if geo in self.success_list:
                    break
                await page.reload()
                await asyncio.sleep(5)
                logger.info(f'刷新 {num} ：{geo}')
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            await browser.close()

    def run(self):
        # # 欧洲
        # countrys = {
        #     'Germany': {'area': 'European region', 'geo': 'DE'},
        #     'France': {'area': 'European region', 'geo': 'FR'},
        #     'Netherlands': {'area': 'European region', 'geo': 'NL'},
        #     'Switzerland': {'area': 'European region', 'geo': 'CH'},
        #     'Belgium': {'area': 'European region', 'geo': 'BE'},
        #     'Austria': {'area': 'European region', 'geo': 'AT'}
        # }
        # 中东
        countrys = {'united arab emirates': {'area': 'Middle East', 'geo': 'AE'},
               'Saudi Arabia': {'area': 'Middle East', 'geo': 'SA'}, 'Egypt': {'area': 'African region', 'geo': 'EG'},
               'morocco': {'area': 'African region', 'geo': 'MA'}, 'Algeria': {'area': 'African region', 'geo': 'DZ'},
               'worldwide': {'area': '', 'geo': ''}, 'Jordan': {'area': 'Jordan', 'geo': 'JO'}}
        for c_name in countrys:
            geo = countrys[c_name]['geo']
            # 近3个月
            # url = f'https://trends.google.com/trends/explore?date=today%203-m&geo={geo}&q=crypto&hl=en-US'
            url = f'https://trends.google.com/trends/explore?date=2023-01-01%202024-04-07&geo={geo}&q=crypto&hl=en-US'
            params = {'name':c_name, 'geo':geo}
            # await self.lanch_chrome(url, params)
            asyncio.run(self.lanch_chrome(url, params))

