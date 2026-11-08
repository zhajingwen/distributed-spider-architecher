import asyncio
import json
import os
import logging
from hashlib import md5
from datetime import datetime
import time
from playwright.async_api import async_playwright
from functools import partial

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GoogleTrends Playwright')
env = os.environ.get('env')
countrys = {
    "South Korea": {
        "area": "East Asia",
        "geo": "KR"
    },
    "Japan": {
        "area": "East Asia",
        "geo": "JP"
    },
    "China": {
        "area": "East Asia",
        "geo": "CN"
    },
    "Hongkong": {
        "area": "Hong Kong, Macao and Taiwan regions",
        "geo": "HK"
    },
    "Macao": {
        "area": "Hong Kong, Macao and Taiwan regions",
        "geo": "MO"
    },
    "Taiwan": {
        "area": "Hong Kong, Macao and Taiwan regions",
        "geo": "TW"
    },
    "Vietnam": {
        "area": "Southeast Asia",
        "geo": "VN"
    },
    "Thailand": {
        "area": "Southeast Asia",
        "geo": "TH"
    },
    "Indonesia": {
        "area": "Southeast Asia",
        "geo": "ID"
    },
    "Malaysia": {
        "area": "Southeast Asia",
        "geo": "MY"
    },
    "Singapore": {
        "area": "Southeast Asia",
        "geo": "SG"
    },
    "Myanmar": {
        "area": "Southeast Asia",
        "geo": "MM"
    },
    "the Philippines": {
        "area": "Southeast Asia",
        "geo": "PH"
    },
    "Cambodia": {
        "area": "Southeast Asia",
        "geo": "KH"
    },
    "India": {
        "area": "South Asia",
        "geo": "IN"
    },
    "Pakistan": {
        "area": "South Asia",
        "geo": "PK"
    },
    "United States": {
        "area": "English area",
        "geo": "US"
    },
    "U.K.": {
        "area": "English area",
        "geo": "GB"
    },
    "Canada": {
        "area": "English area",
        "geo": "CA"
    },
    "Australia": {
        "area": "English area",
        "geo": "AU"
    },
    "Russia": {
        "area": "CIS area",
        "geo": "RU"
    },
    "Ukraine": {
        "area": "CIS area",
        "geo": "UA"
    },
    "Belarus": {
        "area": "CIS area",
        "geo": "BY"
    },
    "Kazakhstan": {
        "area": "CIS area",
        "geo": "KZ"
    },
    "Uzbekistan": {
        "area": "CIS area",
        "geo": "UZ"
    },
    "Turkey": {
        "area": "European region",
        "geo": "TR"
    },
    "Germany": {
        "area": "European region",
        "geo": "DE"
    },
    "France": {
        "area": "European region",
        "geo": "FR"
    },
    "Italy": {
        "area": "European region",
        "geo": "IT"
    },
    "Spain": {
        "area": "European region",
        "geo": "ES"
    },
    "Netherlands": {
        "area": "European region",
        "geo": "NL"
    },
    "Switzerland": {
        "area": "European region",
        "geo": "CH"
    },
    "Poland": {
        "area": "European region",
        "geo": "PL"
    },
    "Belgium": {
        "area": "European region",
        "geo": "BE"
    },
    "united arab emirates": {
        "area": "Middle East",
        "geo": "AE"
    },
    "Saudi Arabia": {
        "area": "Middle East",
        "geo": "SA"
    },
    "Qatar": {
        "area": "Middle East",
        "geo": "QA"
    },
    "Israel": {
        "area": "Middle East",
        "geo": "IL"
    },
    "Argentina": {
        "area": "latin america region",
        "geo": "AR"
    },
    "Brazil": {
        "area": "latin america region",
        "geo": "BR"
    },
    "Mexico": {
        "area": "latin america region",
        "geo": "MX"
    },
    "Uruguay": {
        "area": "latin america region",
        "geo": "UY"
    },
    "Chile": {
        "area": "latin america region",
        "geo": "CL"
    },
    "Colombia": {
        "area": "latin america region",
        "geo": "CO"
    },
    "nigeria": {
        "area": "African region",
        "geo": "NG"
    },
    "South Africa": {
        "area": "African region",
        "geo": "ZA"
    },
    "Egypt": {
        "area": "African region",
        "geo": "EG"
    },
    "morocco": {
        "area": "African region",
        "geo": "MA"
    },
    "Algeria": {
        "area": "African region",
        "geo": "DZ"
    },
    "worldwide": {
        "area": "",
        "geo": ""
    }
}


class Play:
    def __init__(self):
        self.check_key_base = 'googletrends:check:{}'
        self.table = 'google_trends2'

    def insert_data_worldwide(self, data, spider_date, spider_time):
        table = 'google_trends_worldwide'
        all_update_sql_base = "replace into {} values{};"
        sql_values = []
        for d in data:
            related_words = d['query']
            value = d['value']
            value = round(value / 100, 2)
            # 存在一大段句子的情况
            if len(related_words) > 100:
                continue
            if len(related_words.split(' ')) > 5:
                continue
            id = md5(f'{spider_date}{related_words}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(related_words)},{value},{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
        if not data:
            return
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(table, ','.join(sql_values))
            print(all_update_sql)
            return True

    def parse_insert_to_db(self, data, country, spider_date, geo, area, spider_time):
        all_update_sql_base = "replace into {}(id,geo,country,area,related_words,spider_time,spider_date) values{};"
        sql_values = []
        if geo == '':
            status = self.insert_data_worldwide(data, spider_date, spider_time)
            if not status:
                pass
            return
        for d in data:
            related_words = d['query']
            # 存在一大段句子的情况
            if len(related_words) > 100:
                continue
            if len(related_words.split(' ')) > 5:
                continue
            id = md5(f'{country}{spider_date}{related_words}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(geo)},{repr(country)},{repr(area)},{repr(related_words)},{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
            if data.index(d) == 9:
                break
        if not data:
            id = md5(f'{country}{spider_time}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(geo)},{repr(country)},{repr(area)},'',{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
            print(all_update_sql)

    async def on_response(self, params, response):
        """
        hook数据
        """
        geo = params['geo']
        # 校验是否成功的redis key  如果失败这个key会存在
        # key = self.check_key_base.format(geo)
        if 'relatedsearches' in response.url:
            try:
                oridata = await response.text()
                data = oridata.strip().split('\n')[-1]
                data = json.loads(data)
            except:
                logger.error(f'数据拦截异常，未加载进来：{geo}')
                return
            data = data['default']['rankedList'][1]['rankedKeyword']
            # relatedsearches有两个接口，另外一个关联topic过滤
            if data:
                if 'query' not in data[0]:
                    return
            country = params['country']
            spider_date = params['spider_date']
            area = params['area']
            spider_time = params['spider_time']
            self.parse_insert_to_db(data, country, spider_date, geo, area, spider_time)

    async def job(self, url, data):
        """
        启动浏览器
        """
        if env == 'local':
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
        else:
            launch_data = {
                "headless": False,
            }
        async with async_playwright() as p:
            if self.browser_type == 'webkit':
                browser = await p.webkit.launch(**launch_data)
            else:
                browser = await p.chromium.launch(**launch_data)
            page = await browser.new_page()
            # 实现传参给response
            response_handler = partial(self.on_response, data)
            page.on('response', response_handler)
            enable_url = 'https://trends.google.com'
            await page.goto(enable_url, timeout=0)
            await asyncio.sleep(3)
            await page.goto(url, timeout=0)
            geo = data['geo']
            # 校验是否成功的 redis key  成功则该key存在
            success_key = self.check_key_base.format(geo) + ':success'
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            # await page.wait_for_function("() => window.x > 0", timeout=0)
            await browser.close()

    async def lanch_chrome(self, url, data):
        """
        当浏览器启动失败时，进行重试，上限为10次
        """
        num = 0
        while True:
            num += 1
            if num > 10:
                logger.error(f'重试 {num} 次，浏览器依旧无法正常启动')
                break
            try:
                await self.job(url, data)
                break
            except:
                geo = data['geo']
                logger.info(f'浏览器启动失败，重试 {num} {geo}')


    def call_playwright(self, url, data):
        """
        根据环境变量，选择Chrome的启动方式
        """
        asyncio.run(self.lanch_chrome(url, data))

    def task(self, url, data, browser_type):
        """
        接受被main模块调用
        """
        self.browser_type = browser_type
        self.call_playwright(url, data)

    def req(self, country="美国", spider_time=1111, spider_date='None'):
        """
        调用playwright hook数据
        """
        geo = countrys[country]['geo']
        area = countrys[country]['area']
        data = {
            'country':country,
            'spider_date': spider_date,
            'geo': geo,
            'area': area,
            'spider_time': spider_time,
        }
        url = f'https://trends.google.com/trends/explore?q=crypto&date=now%201-d&geo={geo}&hl=en-US&tz=360'
        if not geo:
            url = 'https://trends.google.com/trends/explore?q=crypto&date=now%201-d&hl=en-US&tz=360'
        self.task(url, data, 'webkit')

    def all_country(self):
        """
        采集所有国家
        """
        spider_time = int(time.time())
        spider_date = datetime.now().strftime("%Y-%m-%d")
        for country_name in countrys:
            geo = countrys[country_name]['geo']
            # 补数据
            if geo not in ['']:
                continue
            self.req(country_name, spider_time, spider_date)


if __name__ == '__main__':
    Play().all_country()