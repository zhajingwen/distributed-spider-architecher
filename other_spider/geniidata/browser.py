import json
import logging
import os
import time
import asyncio
from functools import partial
from playwright.async_api import async_playwright
from urllib.parse import quote
from traceback import format_exc
from .gas import GasSpider
from utils.lark_bot import sender
from .runes_parse import ParseRunes

env = os.environ.get('env', 'local')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GeniiData Playwright')

class Geniimap:
    def __init__(self):
        self.url = 'https://geniidata.com/ordinals/home'
        self.alert_time = 0
        self.gas = 0
        self.gasspider = GasSpider()
        self.lark_webhook = os.getenv('LARK_WEBHOOK_GENIIDATA_2', '')

    async def on_response(self, params, response):
        """
        拦截数据
        """
        if 'https://www.geniidata.com/api/btc/ord/flow/minters?' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            items = data['data']['list']
            content_list = []
            for index, item in enumerate(items):
                if index > 2:
                    break
                type = item['type']
                asset = item['asset']
                minters = item['minters']

                params = item['params']
                contentType = params['contentType']
                keyword = params['keyword']
                keyword = quote(keyword)
                url = f'https://geniidata.com/ordinals/inscriptions?q={keyword}&protocol=&content-type={contentType}&time=1D&attribute=&inscription-range=normal&satributes='
                row = f'类型：{type} 资产：{asset} minters：{minters} 详情&url&{url}'
                content_list.append(row)
            item_bar = '\n'.join(content_list)
            gas = f'GAS:{self.gas}'
            if self.gas <= 25:
                hot_degree_content = '热度极低'
            elif 25 < self.gas <= 60:
                hot_degree_content = '热度正常'
            elif 60 < self.gas <= 100:
                hot_degree_content = '稍有热度'
            elif 100 < self.gas <= 200:
                hot_degree_content = '热度较高'
            else:
                hot_degree_content = '热度高'
            content = f'{hot_degree_content}\n' + item_bar
            # 10分钟告警1次
            if int(time.time()) - self.alert_time > 10*60:
                sender(content, self.lark_webhook, gas)
                self.alert_time = int(time.time())
        if 'https://www.geniidata.com/api/btc/ord/flow/rank?p=runes&type=1D' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            logger.info(f'递交给Runes任务做处理：{data}')
            ParseRunes().parse(data)

    async def run_local(self):
        """
        开发环境加载浏览器
        """
        async with async_playwright() as p:
            launch_data = {
                "headless": False,
                "args": ['--start-maximized']
            }
            browser = await p.chromium.launch(**launch_data)
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            # 实现传参给response
            response_handler = partial(self.on_response, "data")
            page.on('response', response_handler)
            await page.goto(self.url, timeout=0)
            await asyncio.sleep(10)
            logger.info('关闭浏览器')
            await browser.close()

    async def run_aws(self):
        from pyvirtualdisplay import Display
        with Display():
            try:
                await self.run_local()
            except:
                logger.error(f'浏览器异常：{format_exc()}')

    def task(self):
        gas = self.gasspider.gas()
        self.gas = gas
        if env == 'local':
            asyncio.run(self.run_local())
        else:
            asyncio.run(self.run_aws())

    def schedule(self):
        logger.info(f'开始进度调度，等待中...')
        while True:
            # 1小时1次
            time.sleep(60*60)
            self.task()


