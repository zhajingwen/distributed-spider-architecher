import time
import json
import logging
import os
import re
import asyncio
from traceback import format_exc
from other_spider.brc20.unisat_playwright.data_machine import Unisat
from playwright.async_api import async_playwright
from cf_clearance import async_cf_retry, async_stealth
from utils.redisdb import redis_cli
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Unisat Playwright')
env = os.environ.get('env')

class UPlaywright:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.stop_turn_page = 'crawl-brc20:unisat_playwright:stopturnpage'
        self.proxy = config.PROXY_URL

    async def on_response(self, response):
        # api.unisat.space/query-v4/brc20/status
        # api.unisat.io/query-v4/brc20/status
        if 'api.unisat.space/query-v4/brc20/status' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            # 区分是哪一个分类页面的
            if 'complete=no' in response.url:
                logger.info(f'mint中 url: {response.url}')
            else:
                logger.info(f'mint全量 url: {response.url}')
            names = []
            for item in data['data']['detail']:
                name = item['ticker']
                names.append(name)
            logger.info(names)
            Unisat().parse(data)

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

    async def run_local(self, jscode, page_num):
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
                    url = 'https://unisat.io/brc20'
                    await page.goto(url)
                    logger.info(f'打开: {url}')
                    res = await async_cf_retry(page)
                    if env == 'local':
                        await asyncio.sleep(20)
                    else:
                        await asyncio.sleep(30)
                    # 等待页面加载完成
                    await page.wait_for_load_state('networkidle')
                    # await asyncio.sleep(3)
                    # mint进行中的
                    if jscode:
                        # 按mint进行中页面排序
                        await page.evaluate(jscode)
                        # 等待页面加载完成
                        await page.wait_for_load_state('networkidle')
                        await asyncio.sleep(5)
                        logger.info('执行完按mint进行中的分类')
                    all_js = """() => {
                      var elements = document.querySelectorAll('div');
                      for (var i = 0; i < elements.length; i++) {
                        if (elements[i].textContent === 'Transactions') {
                          elements[i].click();
                          break;
                        }
                      }
                    }"""
                    logger.info('执行完按transactions排序')
                    # 按transactions排序
                    await page.evaluate(all_js)
                    logger.info('cloudflare验证通过！')
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
            # logger.info('关闭当前页')
            # await page.close()
            logger.info('关闭浏览器')
            await browser.close()
            logger.info('浏览器已关闭！')

    async def run_aws(self, jscode, page_num):
        from pyvirtualdisplay import Display
        with Display():
            try:
                await self.run_local(jscode, page_num)
            except:
                logger.error(f'浏览器异常：{format_exc()}')

    def two_list_page(self, listpage_type):
        """
        in-progress页面 和 All页面
        """
        # mint进行中的，多一个步骤，线切入到in-progress分类
        in_progess_js = """() => {
          var segmentedGroup = document.getElementsByClassName("ant-segmented-group")[0];
          var divElements = segmentedGroup.getElementsByTagName("div");
          for (var i = 0; i < divElements.length; i++) {
            if (divElements[i].textContent === "In-Progress") {
              divElements[i].click();
              break;
            }
          }
        }"""
        # 通常mint进行中的满足transactions>300的只有20页以内
        in_progress_page_num = 25
        if listpage_type == 'inprogress':
            logger.info('执行mint进行中的浏览器进程')
            jscode = in_progess_js
            page_num = in_progress_page_num
        else:
            logger.info('执行mint完成的浏览器进程')
            jscode = None
            page_num = 60
        # for
        if env == 'local':
            asyncio.run(self.run_local(jscode, page_num))
        else:
            asyncio.run(self.run_aws(jscode, page_num))

    def run(self):
        while True:
            for t in ['inprogress', 'all']:
                logger.info(f'mint {t}')
                self.two_list_page(t)
            #每10M轮一次
            time.sleep(10*60)
