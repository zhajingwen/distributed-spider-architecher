import time
import json
import logging
import os
import ccxt
import re
import asyncio
from traceback import format_exc
from playwright.async_api import async_playwright
from cf_clearance import async_cf_retry, async_stealth
from lxml.etree import HTML
from retry import retry
from config import config
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies

"""
2024年4月7日无法绕过CLOUDflare的验证，决定放弃；
"""
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gate Playwright')
env = os.environ.get('env')
if not env:
    env = 'local'

class NewCoinPlaywright:
    """
    加载Gate新币清单
    """
    def __init__(self, market, start_time, end_time):
        self.url = 'https://www.gate.io/zh/price/view/new-cryptocurrencies'
        self.redis_cli = redis_cli()
        self.symbols_key = f'coingecko_once:{market}:symbols'
        self.start_time = start_time
        self.end_time = end_time
        self.capture = f'coingecko_once:{market}:capturestatus'
        self.proxy = config.PROXY_URL

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
            logger.info(proxy_params)
        else:
            proxy_params = {"server": proxy}
        return proxy_params

    @retry(tries=6, delay=3)
    def ccxt_one_pair(self, pair, limit, star_time, end_time):
        """
        pair: str 交易对
        limit：int 采集的K线条数  要超出本季度的时间区间
        return: False or 字符串类型的日期
        """
        if env == 'local':
            exchange = ccxt.gate()
        else:
            exchange = ccxt.gate({'proxies': proxies})
        timeframe = '1d'
        try:
            ohlcv_data = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        except:
            error = format_exc()
            # 很多币清单中有，但是实际没上线，这就很怪
            if 'does not have market symbol' in error:
                logger.info(f'没有该币对：{pair}')
                return False
            else:
                raise Exception(error)
        # 最早一更k线对应的日期 是否落在季度内
        # 13位的
        timestamp = ohlcv_data[0][0]/1000
        if (timestamp >= star_time) and (timestamp <= end_time):
            timeArray = time.localtime(timestamp)
            # 使用 strftime 将时间格式化为字符串类型的日期
            listing_time = time.strftime("%Y-%m-%d %H:%M", timeArray)
            return listing_time
        else:
            return False

    def ccxt_judge_target_coin(self, pair, star_time, end_time):
        """
        生成获取K线数据的limit 变量，并请求ccxt
        pair: str 交易对
        star_time：int 本季度开始的1号0点时间对应的时间戳
        return: False or 字符串类型的日期
        """
        days = (int(time.time()) - star_time)/(24*60*60)
        # 为了保险在区间外多加3天，实际上会拿到季度前边界外的多余3天
        limit = int(days) + 3
        # 通过ccxt 判断该币是否是在季度统计内上线的 有值  表示是的
        tartget_coin_status = self.ccxt_one_pair(pair, limit, star_time, end_time)
        return tartget_coin_status

    async def data_deal(self, coin_list):
        """
        解析数据并入库
        """
        logger.info(f'捕获到数据：{coin_list}')
        for item in coin_list:
            # = 0 才表示正经上线的
            buy_start_timest = item['buy_start_timest']
            symbol = item['symbol']
            if buy_start_timest != 0:
                logger.info(f'该币尚未上线：{symbol}')
                continue
            # 存在就跳过，不重复刷新
            exsit_status = self.redis_cli.hget(self.symbols_key, symbol)
            if exsit_status:
                logger.info(f'已经载入过了：{symbol}')
                continue
            name = item['name']
            pair = f"{item['curr_a']}/{item['curr_b']}"
            # 判断币是否是统计区间内上的
            status = self.ccxt_judge_target_coin(pair, self.start_time, self.end_time)
            if not status:
                logger.info(f'非统计季度内的币：{pair}')
                continue
            listing_time = status
            result = {
                'name': name,
                'symbol': symbol,
                'pair': pair,
                'listing_time': listing_time,
                # 该键值对会激活 coingecko search匹配
                'coingecko_match': False
            }
            self.redis_cli.hset(self.symbols_key, symbol, json.dumps(result))

    async def parse_html(self, html):
        """
        从HTML中解析出数据
        """
        tree = HTML(html)
        print(html)
        result = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if result:
            data = result[0]
            data = json.loads(data)
            coin_list = data['props']['pageProps']['coinNew']['list']
            await self.data_deal(coin_list)

    async def on_response(self, response):
        """
        拦截数据
        """
        if 'https://www.gate.io/market_price/get_coin_list' in response.url:
            if not response.ok:
                logger.error('页面加载异常！')
                return
            try:
                body = await response.body()
            except:
                logger.error(f'抓包解析失败: {response.url}')
                return
            # 捕获到记录状态， 并设置10M过期时间避免对下一次循环造成影响
            self.redis_cli.setex(self.capture, 10*60, 1)
            data = json.loads(body)
            coin_list = data['data']['data']
            logger.info(f'url: {response.url}')
            await self.data_deal(coin_list)
        # html中解析数据
        if response.url == 'https://www.gate.io/zh/price/view/new-cryptocurrencies':
            html = await response.body()
            html = html.decode()
            if '__NEXT_DATA__' in html:
                # 捕获到记录状态， 并设置10M过期时间避免对下一次循环造成影响
                self.redis_cli.setex(self.capture, 10 * 60, 1)
                logger.info(f'url: {response.url}')
                await self.parse_html(html)

    async def run_local(self):
        """
        开发环境加载浏览器
        """
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
            browser = await p.webkit.launch(**launch_data)
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});")
            page.on('response', self.on_response)
            num_retries = 0
            while True:
                try:
                    await async_stealth(page, pure=True)
                    logger.info('async_stealth Done')
                    await page.goto(self.url)
                    logger.info(f'打开: {self.url}')
                    res = await async_cf_retry(page)
                    # 等待页面加载完成
                    if env == 'local':
                        await asyncio.sleep(20)
                    else:
                        await asyncio.sleep(30)
                    if res:
                        # 等待页面加载完成
                        await page.wait_for_load_state('networkidle')
                        await asyncio.sleep(3)
                        await page.reload(wait_until='domcontentloaded')
                        res = await async_cf_retry(page)
                        logger.info(f'res: {res}')
                        # 再次确认是否加载成功了
                        status = self.redis_cli.get(self.capture)
                        if status:
                            logger.info('成功捕获数据（redis记录）')
                            break
                        else:
                            logger.error(f'cloudflare 验证失败，重试...')
                            num_retries += 1
                            if num_retries > 10:
                                logger.error('重试超过次数，无法绕过cloudflare验证！跳出！')
                                break
                            time.sleep(10)
                except:
                    logger.error(f'浏览器异常：{format_exc()}')
                    time.sleep(10)
            logger.info('关闭浏览器')
            await browser.close()
            logger.info('浏览器已关闭！，60M后重新启动...')

    async def run_aws(self):
        """
        服务器加载浏览器
        """
        from pyvirtualdisplay import Display
        with Display():
            try:
                await self.run_local()
            except:
                logger.error(f'浏览器异常：{format_exc()}')

    def run(self):
        while True:
            if env == 'local':
                asyncio.run(self.run_local())
            else:
                asyncio.run(self.run_aws())
            # 每1H轮一次
            time.sleep(60 * 60)
