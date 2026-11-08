import os
import csv
import time
import json
import logging
from playwright.sync_api import sync_playwright
from traceback import print_exc
from utils.redisdb import redis_cli
from utils.rds import DataUtils


# 登录后的浏览器 cookies（JSON 数组），通过环境变量 NANSEN_COOKIES 传入
logined_cookies = json.loads(os.getenv('NANSEN_COOKIES', '[]'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Nansen Ftx')


class Nansen:

    def __init__(self):
        self.redis_cli = redis_cli()
        self.crypto_scan_job_key = 'crypto:scan:jobs_backup'
        self.rds = DataUtils('spider')

    def parse_list(self, page, job):
        logger.info(f'job: {job}')
        click_button = '//span[text()="Show More"]'
        try:
            page.locator(click_button).click()
            # page.wait_for_selector(click_button,state="visible")
            elements_pattern = '//div[@class="sc-bXRjm sc-fZDhWb bQbSVD jFrMaO"]/span'
            page.wait_for_selector(elements_pattern, state="visible")
            data_list = page.query_selector_all(elements_pattern)
        except:
            logger.warning('没有跟多选项')
            # 这里可能存在报错的情况
            data_list = page.query_selector_all('//div[@class="sc-bXRjm bQbSVD"]/span')
        tags = []
        for element in data_list:
            tag = element.query_selector('xpath=./span').text_content()
            tags.append(tag)
        logger.info(f'采集到的tags: {tags}')
        # 格式化数据方便存入mysql
        names = job['name']
        new_tags = ','.join(tags)
        id = job['id']
        select_sql = f'select id,names,tags from crypto_scan where id="{id}";'
        s_result = self.rds.select(select_sql)
        logger.info(f'数据库查询结果：{s_result}')
        # 新增name和tag到已有的记录中
        if s_result:
            old_names = s_result[0]['names']
            old_tags = s_result[0]['tags']
            new_old_names = old_names.split(',')
            new_old_tags = old_tags.split(',')
            if job['name'] not in old_names:
                new_old_names.append(job['name'])
            for tag in tags:
                if tag not in new_old_tags:
                    new_old_tags.append(tag)
            names = ','.join(new_old_names)
            new_tags = ','.join(new_old_tags)

        blockchain = job['blockchain']
        address = job['address']
        replace_into_sql = f"replace into crypto_scan(id,blockchain,address,names,tags) values('{id}','{blockchain}','{address}','{names}','{new_tags}');"
        logger.info(replace_into_sql)
        self.rds.insert(replace_into_sql)

    def consumer(self):
        num = 0
        url_base = 'https://pro.nansen.ai/wallet-profiler?address={}'
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(logined_cookies)
            page = context.new_page()
            while True:
                job = self.redis_cli.spop(self.crypto_scan_job_key)
                if not job:
                    time.sleep(10)
                    logger.warning('当前没有任务')
                    continue
                job = json.loads(job)
                num += 1
                logger.info(f'第{num}个任务')
                blockchain = job['blockchain']
                if blockchain == 'ETH':
                    url = url_base.format(job['address'])
                elif blockchain == 'BSC':
                    url = url_base.format(job['address']) + '&network=bsc'
                    # polygon
                else:
                    url = url_base.format(job['address']) + '&network=polygon'
                # 永不超时，等待连接建立
                # 这里也可能报错，具体原因不清楚  playwright._impl._api_types.Error: Navigation failed because page crashed!
                page.goto(url, timeout=0)
                try:
                    self.parse_list(page, job)
                except:
                    logger.error(f'无法解析页面：{url}   跳过')
                    print_exc()
                    time.sleep(10)
                # page.wait_for_function("() => window.x > 0", timeout=0)

    def run(self):
        while True:
            try:
                self.consumer()
                logger.info('循环跑完了...')
                break
            except:
                print_exc()
                logger.error('浏览器故障，重启...')
                time.sleep(3)

    # def createt(self):
    #     self.rds.create_table()

# if __name__ == '__main__':
#   Nansen().createt()
