import time
import json
import logging
import os
import re
import asyncio
from traceback import format_exc
from config import config
from playwright.async_api import async_playwright
from cf_clearance import async_cf_retry, async_stealth
from utils.redisdb import redis_cli
from .parse_alert import Parse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Unisat Runes Playwright')
env = os.environ.get('env')

class List:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.stop_turn_page = 'runes:stopturnpage'
        self.proxy = config.PROXY_URL

    async def on_response(self, response):
        # https://api-testnet.unisat.io/query-v4/runes/info-list?rune=&start=0&limit=20&complete=&sort=minted
        if 'api-testnet.unisat.io/query-v4/runes/info-list' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            runes = []
            for item in data['data']['detail']:
                rune = item['rune']
                runes.append(rune)
            logger.info(runes)
            Parse().parse(data)

    def _parse_proxy(self, proxy: str):
        """
        格式化代理，转换成字典的结构
        """
        if "@" in proxy:
            proxy_regex = re.match("(.+)://(.+):(.+)@(.+)", proxy)
            server = f"{proxy_regex.group(1)}://{proxy_regex.group(4)}"

            proxy_params = {
                "server": server,
                "username": proxy_regex.group(2),
                "password": proxy_regex.group(3),
            }
            print(proxy_params)
        else:
            proxy_params = {"server": proxy}
        return proxy_params

    async def run_local(self):
        page_num = 100
        num = 1
        async with async_playwright() as p:
            if env == 'local':
                launch_data = {
                    "headless": False
                }
            else:
                launch_data = {
                    "headless": False,
                    "proxy": self._parse_proxy(self.proxy)
                }
            # browser = await p.chromium.launch(headless=False)
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            page.on('response', self.on_response)
            while True:
                try:
                    await async_stealth(page, pure=True)
                    url = 'https://testnet.unisat.io/runes/list'
                    await page.goto(url)
                    logger.info(f'打开: {url}')
                    res = await async_cf_retry(page)
                    if env == 'local':
                        await asyncio.sleep(20)
                    else:
                        await asyncio.sleep(30)
                    # 等待页面加载完成
                    await page.wait_for_load_state('networkidle')
                    # logger.info('cloudflare验证通过！')
                    break
                except:
                    logger.error(f'cloudflare 验证失败，重试...')
            if res:
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
                    # 故当num > page_num 时跳出
                    if num > page_num:
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
            logger.info('关闭浏览器')
            await browser.close()
            logger.info('浏览器已关闭！')

    async def run_aws(self):
        from pyvirtualdisplay import Display
        with Display():
            try:
                await self.run_local()
            except:
                logger.error(f'浏览器异常：{format_exc()}')

    def job(self):
        """
        in-progress页面 和 All页面
        """
        if env == 'local':
            asyncio.run(self.run_local())
        else:
            asyncio.run(self.run_aws())

    def run(self):
        while True:
            self.job()
            #每1小时轮一次
            time.sleep(60*60)
