from config.exchange import EXCHANGE_SYMBOL_PARTITION_URL, spot_page_url
import asyncio
import time
import json
import logging
from playwright.async_api import async_playwright
from pyvirtualdisplay import Display
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Playwright Listing Inno')

class Play:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.redis_marketpairs_key = 'mainex:marketpairs'
        self.url = spot_page_url('GHSTUSDT')

    # async def on_response(self, response):
    #     if EXCHANGE_SYMBOL_PARTITION_URL in response.url:
    #         oridata = await response.body()
    #         format_data = json.loads(oridata)
    #         # url = response.url
    #         coin_list = format_data['data'][0]['categories'][1]['symbolList']
    #         with self.redis_cli.pipeline(transaction=False) as pipe:
    #             for marketpair in coin_list:
    #                 if '_' in marketpair:
    #                     marketpair = marketpair.replace('_', '/')
    #                 else:
    #                     marketpair = marketpair.replace('USDT', '/USDT')
    #                 # print(marketpair)
    #                 pipe.hset(self.redis_marketpairs_key,marketpair,1)
    #             pipe.execute()
    #         marketpairs = self.redis_cli.hkeys(self.redis_marketpairs_key)
    #         logger.info(marketpairs)
    async def on_response(self, response):
        if EXCHANGE_SYMBOL_PARTITION_URL and EXCHANGE_SYMBOL_PARTITION_URL in response.url:
            logger.info(f'捕获数据接口: {response.url}')
            oridata = await response.body()
            format_data = json.loads(oridata)
            categories = format_data['data'][0]['categories']
            with self.redis_cli.pipeline(transaction=False) as pipe:
                for category in categories:
                    coin_list = category['symbolList']
                    for marketpair in coin_list:
                        if '_' in marketpair:
                            marketpair = marketpair.replace('_', '/')
                        else:
                            marketpair = marketpair.replace('USDT', '/USDT')
                        pipe.hset(self.redis_marketpairs_key,marketpair,1)
                    pipe.execute()
            marketpairs_length = self.redis_cli.hlen(self.redis_marketpairs_key)
            logger.info(f'交易对总量：{marketpairs_length}')

    async def open_site(self):
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

        with Display():
            async with async_playwright() as p:
                browser = await p.chromium.launch(**launch_data)
                page = await browser.new_page()
                page.on('response', self.on_response)
                await page.goto(self.url)
                # time.sleep(5)
                # await page.screenshot(path='test.png')
                time.sleep(30)
                await browser.close()

    def run(self):
        # 用redis来做消息队列，通知复核程序检查，任务是否全部跑完了
        # self.redis_cli.sadd(self.redis_dappradar_key,int(time.time()))
        while True:
            logger.info('刷新币对列表')
            try:
                asyncio.run(self.open_site())
                # run every 10m
                time.sleep(10 * 60)
            except:
                logger.info('链接访问失败，重试...')
                time.sleep(3)



if __name__ == '__main__':

    Play().run()