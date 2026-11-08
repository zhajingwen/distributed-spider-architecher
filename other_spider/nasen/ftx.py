import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Google Trends')


with sync_playwright() as p:
  browser = p.chromium.launch(headless=False)
  context = browser.new_context()
  page = context.new_page()
  url = 'https://trends.google.com/trends/explore?q=crypto&date=now%201-d&geo=SG&hl=zh-CN'
  page.goto(url,timeout=0)
  # page.locator('//*[@id="email"]').type('user@example.com',delay=100)
  # page.locator('//*[@id="password"]').type('BAIFENGXIAO',delay=100)
  time.sleep(0.5)
  # page.locator('//*[@type="submit"]').click()
  time.sleep(5)
  page.wait_for_load_state('networkidle')
  cookies = context.cookies()
  print(cookies)
  page.goto(url,timeout=0)

  # timeout=0表示永远不超时，以此来确保标签页和浏览器都不会关闭
  page.wait_for_function("() => window.x > 0", timeout=0)

