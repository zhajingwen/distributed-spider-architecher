import os
import json
import csv
import time
import logging
from playwright.sync_api import sync_playwright


# 登录后的浏览器 cookies（JSON 数组），通过环境变量 NANSEN_COOKIES 传入
logined_cookies = json.loads(os.getenv('NANSEN_COOKIES', '[]'))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Nansen Ftx')


def parse_list(page):
  elements_pattern = '//div[@data-scroll="left"]/div[@class="sc-ciFQTS sc-kHdrYz sc-bzPmhk bCbkOs eCZqsZ iQsGuB"]'
  page.wait_for_selector(elements_pattern,state="visible")
  data_list = page.query_selector_all(elements_pattern)
  rows = []
  for element in data_list:
    tag = element.query_selector('xpath=./a/div[2]/span/span/span').text_content()
    url = element.query_selector('xpath=./a').get_attribute('href')
    id = url.split('address=')[-1]
    balance = element.query_selector('xpath=./div[@data-column="1"]/div[1]/span/span').text_content()
    ownership = element.query_selector('xpath=./div[@data-column="2"]/div/span/span').text_content()
    row = [tag,id,balance,ownership]
    rows.append(row)
  return rows

with sync_playwright() as p:
  browser = p.chromium.launch(headless=False)
  context = browser.new_context()
  context.add_cookies(logined_cookies)
  page = context.new_page()
  url = 'https://pro.nansen.ai/token-god-mode/notable?token_address=0x50d1c9771902476076ecfc8b2a83ad6b9355a4c9'
  # 永不超时，等待连接建立
  page.goto(url,timeout=0)
  with open('result.csv','w',encoding='utf-8-sig',newline='')as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['tag','id','balance','ownership'])
    rows = parse_list(page)
    writer.writerows(rows)
    for i in range(67):
      logger.info(i)
      try:
        page.locator('//button[@data-cy="tgm-top-balances-page-right-button"]').click()
      except:
        logger.warning(f'done:{i}')
        break
      time.sleep(1)
      next_rows = parse_list(page)
      writer.writerows(next_rows)

  page.wait_for_function("() => window.x > 0", timeout=0)


