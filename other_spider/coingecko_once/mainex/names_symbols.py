from config.exchange import EXCHANGE_MARKETS_PAGE_URL, EXCHANGE_COIN_CHAIN_URL_KEYWORD
import asyncio
import time
import json
import logging
import os
from traceback import format_exc
from playwright.async_api import async_playwright
# from pyvirtualdisplay import Display
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mainex Playwright')
env = os.environ.get('env')

class NameSymbol:
    """
    生成全站name symbol的对应关系
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        # hash
        self.idnamess_key = 'mainex:idsnames'
        # hash
        self.symbolids_key = 'mainex:symbolids'
        self.url = EXCHANGE_MARKETS_PAGE_URL
        # set 给mainex 》 newcoin.py消费
        self.newcoin_alert_jobs = 'mainex:newcoin:alert:jobs'

    async def on_response(self, response):
        """
        拦截响应
        """
        if EXCHANGE_COIN_CHAIN_URL_KEYWORD and EXCHANGE_COIN_CHAIN_URL_KEYWORD in response.url:
            logger.info(f'捕获数据接口: {response.url}')
            oridata = await response.body()
            format_data = json.loads(oridata)
            new_data = {}
            ids = []
            id_name_map = {}
            with self.redis_cli.pipeline(transaction=False)as pipe:
                for item in format_data['data']['item']:
                    try:
                        symbol = item['coinName']
                        name = item.get('fullName',symbol)
                        # 生成告警任务 给另外的程序消费
                        self.redis_cli.sadd(self.newcoin_alert_jobs, f'{name}/{symbol}')
                        # 有些value事空字符串
                        if not name:
                            name = symbol
                        if name in new_data:
                            logger.info(f'name重复：{name}')
                        # 递增关系，越晚上币coinId越大
                        coinId = item['coinId']
                        ids.append(coinId)
                        id_name_map[id] = name
                        # logger.info(f'coinId: {coinId}')
                        pipe.hset(self.idnamess_key, coinId, name)
                        pipe.hset(self.symbolids_key, symbol, coinId)
                        new_data[name] = symbol
                    except:
                        logger.info(item)
                pipe.execute()
            # 打印最新上的一个币
            max_id = max(ids)
            max_name = id_name_map[id]
            logger.info(f'max id: {max_id} {max_name}')
            logger.info(f'所有币入库')
            # 优化内存
            del new_data
            del ids
            del id_name_map

    async def run_local(self):
        async with async_playwright() as p:
            launch_data = {
                "headless": False
            }
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            page.on('response', self.on_response)
            await page.goto(self.url)
            await asyncio.sleep(30)
            # 等待页面加载完成
            # await page.wait_for_load_state('networkidle')
            logger.info('关闭浏览器')
            await browser.close()
            logger.info('浏览器已关闭！，24H后重新启动...')


    async def run_aws(self):
        from pyvirtualdisplay import Display
        with Display():
            try:
                await self.run_local()
            except:
                logger.error(f'浏览器异常：{format_exc()}')

    def run(self):
        while True:
            try:
                if env == 'local':
                    asyncio.run(self.run_local())
                else:
                    asyncio.run(self.run_aws())
                #每 1H 刷一次
                time.sleep(1*60*60)
            except:
                # 当程序异常的时候等1分钟后重启
                time.sleep(60)



if __name__ == '__main__':

    NameSymbol().run()