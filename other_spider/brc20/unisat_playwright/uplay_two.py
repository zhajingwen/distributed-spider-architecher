import time
import json
import logging
import os
import asyncio
from traceback import format_exc
from other_spider.brc20.unisat_playwright.data_machine import Unisat
from playwright.async_api import async_playwright
from cf_clearance import async_cf_retry, async_stealth
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Unisat Playwright')
env = os.environ.get('env')

class UPlaywright:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.stop_turn_page = 'crawl-brc20:unisat_playwright:stopturnpage'

    async def on_response(self, response):
        if 'api.unisat_playwright.io/query-v4/brc20/status' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            logger.info(f'url: {response.url}')
            names = []
            for item in data['data']['detail']:
                name = item['ticker']
                names.append(name)
            logger.info(names)
            Unisat().parse(data)

    async def browser(self):
        num = 1
        async with async_playwright() as p:
            launch_data = {
                "headless": True
            }
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            page.on('response', self.on_response)
            await async_stealth(page, pure=True)
            await page.goto('https://unisat.io/brc20')
            res = await async_cf_retry(page)
            if res:
                await asyncio.sleep(3)
                # 按transactions排序
                await page.evaluate('''() => {
                    var elements = document.querySelectorAll('div');
                    for (var i = 0; i < elements.length; i++) {
                      if (elements[i].textContent === 'Transactions') {
                        elements[i].click();
                        break;
                      }
                    }
                }''')
                # 等待页面加载完成
                await page.wait_for_load_state('networkidle')
                await asyncio.sleep(3)
                logger.info(f'第 {num} 页')
                logger.info('准备执行翻页...')
                # 翻页循环
                while True:
                    num += 1
                    # 停止翻页  仅仅根据该条件，有可能会陷入死循环
                    # 常规来说翻到53页就会跳出，2023年11月9日，陷入过死循环
                    status = self.redis_cli.get(self.stop_turn_page)
                    if status:
                        break
                    # 为了避免死循环的发生，双保险策略，再加一条跳出规则，观察发现当60页以后基本transacions数量就小于300了，
                    # 故当num > 60 时跳出
                    if num > 60:
                        logger.warning(f'已经翻到了 {num} 页，跳出！')
                        break
                    # 执行JavaScript代码 翻页
                    await page.evaluate('''() => {
                        var button = document.querySelector('.ant-pagination-next');
                        button.click();
                    }''')
                    # 等待页面加载完成
                    await page.wait_for_load_state('networkidle')
                    logger.info(f'第 {num} 页')
                    # 等待 3 秒钟
                    await asyncio.sleep(3)
                # 初始化
                self.redis_cli.delete(self.stop_turn_page)
            else:
                print("cloudflare ban")
            logger.info(f'翻页结束，共 {num} 页')
            logger.info('关闭当前页')
            await page.close()
            logger.info('关闭浏览器')
            await browser.close()
            logger.info('浏览器已关闭！，1小时后重新启动...')

    def run(self):
        while True:
            asyncio.run(self.browser())
            #每小时轮一次
            time.sleep(60*60)
