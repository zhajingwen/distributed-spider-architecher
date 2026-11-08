import asyncio
import json
import os
import logging
import time
from playwright.async_api import async_playwright
# from traceback import format_exc
from threading import Thread
from functools import partial
from .parse import ParseData
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

    async def on_response(self, params, response):
        """
        hook数据
        """
        geo = params['geo']
        # 校验是否成功的redis key  如果失败这个key会存在
        key = self.check_key_base.format(geo)
        if 'relatedsearches' in response.url:
            logger.info(f'捕获数据接口: {geo}')
            try:
                oridata = await response.text()
                data = oridata.strip().split('\n')[-1]
                data = json.loads(data)
            except:
                logger.error(f'数据拦截异常，未加载进来：{geo}')
                # logger.error(f'{format_exc()}')
                self.redis_cli.set(key, 1)
                return
            data = data['default']['rankedList'][1]['rankedKeyword']
            # relatedsearches有两个接口，另外一个关联topic过滤
            if data:
                if 'query' not in data[0]:
                    return
            logger.info(data)
            country = params['country']
            spider_date = params['spider_date']
            area = params['area']
            spider_time = params['spider_time']
            ParseData().parse_insert_to_db(data, country, spider_date, geo, area, spider_time)
            # 成功的条件下且存在这个key，则删除
            if self.redis_cli.get(key):
                self.redis_cli.delete(key)
            success_key = self.check_key_base.format(geo) + ':success'
            # successfully 成功后做标记，就不再重试了，为了防止对次日的任务产生影响，故设置过期时间为60s
            self.redis_cli.setex(success_key,60*60,1)


    async def lanch_chrome(self, url, data):
        """
        启动浏览器
        """
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
            # browser = await p.chromium.launch(**launch_data)
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            # 实现传参给response
            response_handler = partial(self.on_response, data)
            page.on('response', response_handler)
            enable_url = 'https://trends.google.com'
            await page.goto(enable_url, timeout=0)
            await asyncio.sleep(3)
            await page.goto(url, timeout=0)
            # if env == 'local':
            num = 0
            while num < 10:
                num += 1
                await page.reload()
                await asyncio.sleep(10)
                geo = data['geo']
                # 成功后则跳出
                success_key = self.check_key_base.format(geo) + ':success'
                if self.redis_cli.get(success_key):
                    break
                logger.info(f'刷新 {num} ：{geo}')
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            # await page.wait_for_function("() => window.x > 0", timeout=0)
            await browser.close()

    async def open_site_prod(self, url, data):
        """
        线上调用
        """
        from pyvirtualdisplay import Display
        with Display():
            await self.lanch_chrome(url, data)

    def call_playwright(self, url, data):
        """
        根据环境变量，选择Chrome的启动方式
        """
        if env == 'local':
            asyncio.run(self.lanch_chrome(url, data))
        else:
            asyncio.run(self.open_site_prod(url, data))

    def check(self, url, data):
        """
        60s 后校验是否采集成功，成功则跳出，失败则重试
        最多重试3次
        """
        geo = data['geo']
        # 校验是否成功的redis key  如果失败这个key会存在
        key = self.check_key_base.format(geo)
        num = 0
        while True:
            # 失败三次则放弃，避免陷入死循环
            if num > 3:
                sender(f'{geo} 异常', self.web_hook, '失败')
                break
            # 60浏览器一次访问任务应该是执行完了
            time.sleep(60)
            # 失败
            if self.redis_cli.get(key):
                num += 1
                logger.info(f'浏览器访问失败，准备重试，第 {num} 次')
                self.call_playwright(url, data)
            else:
                logger.info(f'采集成功：{geo}')
                break

    def run(self, url, data, browser_type):
        """
        接受被main模块调用
        """
        self.call_playwright(url, data)
        # 异步调用校验机制
        t = Thread(target=self.check, args=(url, data,))
        t.start()