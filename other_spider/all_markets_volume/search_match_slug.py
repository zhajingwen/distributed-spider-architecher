import json
import logging
import csv
import asyncio
from functools import partial
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Playwright')

class NewCoinPlaywright:
    """
    加载Gate新币清单
    """
    def __init__(self):
        self.url = 'https://coinmarketcap.com'
        self.now_name = None
        self.map_slug = {}


    async def on_response(self, params, response):
        """
        拦截数据
        """
        if 'https://api.coinmarketcap.com/gravity/v4/gravity/global-search' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            data = json.loads(body)
            # print(data)
            suggestions = data['data'].get('suggestions')
            if not suggestions:
                return
            for item in suggestions:
                type = item['type']
                matched_status = None
                if type == 'token':
                    tokens = item['tokens']
                    for token in tokens:
                        token_symbol = token['symbol']
                        if self.now_name == token_symbol:
                            matched_status = token['slug']
                            self.map_slug[self.now_name] = token['slug']
                        if matched_status:
                            break
                if matched_status:
                    break
                if type == 'account':
                    # 当 type 是 token 类型匹配不成功的时候用 account匹配
                    if not matched_status:
                        accounts = item['accounts']
                        for account in accounts:
                            projectInfos = account['projectInfos']
                            for projectInfos in projectInfos:
                                token_symbol = projectInfos['symbol']
                                if self.now_name == token_symbol:
                                    matched_status = projectInfos['slug']
                                    self.map_slug[self.now_name] = projectInfos['slug']
                                if matched_status:
                                    break
                            if matched_status:
                                break
                if matched_status:
                    break

    async def search_project(self, page, name):
        # project_name = item['name']
        # 输入搜索关键词
        await page.type('input[type="text"]', name, delay=100)
        await asyncio.sleep(10)
        # 清空搜索框
        search_input = page.locator('input[type="text"]').first
        await search_input.clear()

    def read_source_data(self):
        """
        加载任务
        """
        symbols = []
        with open('source.csv')as f:
            reader = csv.reader(f)
            for row in reader:
                symbol = row[2]
                if symbol not in symbols:
                    symbols.append(symbol)
        # print(symbols)
        symbols = ['ALPHA1', 'BABYDOGE', 'BABYDOGE2', 'BTCMEME', 'CAL1', 'FERC', 'GRIMACE', 'IQ50', 'JOECOIN', 'L', 'MEMECOIN', 'MONG', 'PEPE1', 'PEPE2', 'PEPECOMMUNITY', 'PEPES', 'POGAI', 'SHIBAI', 'VMPXERC20', 'XRP8', 'XXX']

        return symbols


    async def search_loops(self, page):
        """
        为所有的项目做匹配
        """
        symbols = self.read_source_data()
        num = 0
        for symbol in symbols:
            num += 1
            print(f'{num} 准备处理：{symbol}')
            self.now_name = symbol
            await self.search_project(page, symbol)
            print(self.map_slug)

    async def run_local(self):
        """
        开发环境加载浏览器
        """
        # symbols = self.read_source_data()
        async with async_playwright() as p:
            # if env == 'local':
            launch_data = {
                "headless": False,
                "args": ['--start-maximized']
            }
            browser = await p.chromium.launch(**launch_data)
            # page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            # 实现传参给response
            response_handler = partial(self.on_response, "data")
            page.on('response', response_handler)
            # page.on('response', self.on_response)
            await page.goto(self.url, timeout=0)
            logger.info(f'打开: {self.url}')
            await asyncio.sleep(3)
            # 点击搜索框
            js = """
            var element = document.evaluate("//div[text()='Search']", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (element) {
                element.click();
            } else {
                console.log('未找到文本属性为"Search"的div元素');
            }
            """
            await page.evaluate(js)
            await asyncio.sleep(3)
            # 遍历所有项目
            await self.search_loops(page)
            await asyncio.sleep(10)
            logger.info('关闭浏览器')
            await browser.close()

    def run(self):
        # self.read_source_data()
        asyncio.run(self.run_local())

if __name__ == '__main__':
    NewCoinPlaywright().run()