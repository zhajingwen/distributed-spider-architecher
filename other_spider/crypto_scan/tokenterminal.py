import time
import json
import logging
from hashlib import md5
from utils.redisdb import redis_cli
from playwright.sync_api import sync_playwright
from traceback import print_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TokenTerminal Spider')

class TokenTerminal:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.crypto_scan_job_key = 'crypto:scan:jobs_backup'
        self.num = 0

    def on_response(self,response):
        if 'https://api.tokenterminal.com/v2/internal/sql' in response.url:
            if response.request.method == 'POST':
                payload = json.loads(response.request.post_data)
                chain = payload['chain']
                data = json.loads(response.body())
                if chain == 'polygon':
                    chain = 'POLYGON'
                    # print(data)
                    logger.info('POLYGON')
                elif chain == 'bsc':
                    chain = 'BSC'
                    # print(data)
                    logger.info('BSC')
                else:
                    logger.warning('非目标公链')
                    return
                self.num += 1
                with self.redis_cli.pipeline(transaction=False)as pipe:
                    for d in data['data']:
                        address = d['address']
                        title = d['title']
                        # title存在为None的情况
                        if not title:
                            title = ''
                        id = md5(f'{chain}{address}'.encode()).hexdigest()
                        result = {
                            'id': id,
                            'blockchain':chain,
                            'address':address,
                            'name': title
                        }
                        pipe.sadd(self.crypto_scan_job_key, json.dumps(result))
                    pipe.execute()

    def click_event(self, page):
        page.locator('//button[text()="Polygon"]').click()
        time.sleep(1)
        page.locator('//button[text()="30D"]').click()
        time.sleep(1)
        page.locator('//button[text()="7D"]').click()
        time.sleep(1)
        page.locator('//button[text()="24H"]').click()
        time.sleep(1)
        page.locator('//button[text()="BSC"]').click()
        time.sleep(1)
        page.locator('//button[text()="24H"]').click()
        time.sleep(1)
        page.locator('//button[text()="7D"]').click()
        time.sleep(1)
        page.locator('//button[text()="30D"]').click()
        # time.sleep(10)

    def browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # 抓包程序，类似于挂载脚本抓包，解析包内容
            page.on('response', self.on_response)
            url = 'https://tokenterminal.com/terminal/contracts/trending'
            page.goto(url, timeout=0)
            self.click_event(page)
            try:
                page.wait_for_function("() => window.x > 0", timeout=10000)
            except:
                pass
            # time.sleep(10)
            page.close()
            browser.close()

    def run(self):
        # 15分钟跑一次，考虑到执行比较耗时，就改成了14分钟
        while True:
            try:
                self.browser()
                time.sleep(14*60)
            except:
                logger.warning('浏览器异常，重试...')
                print_exc()
                time.sleep(3)