import requests
import logging
import time
import os
from functools import wraps
from traceback import format_exc
from lxml import etree
from datetime import datetime, timezone, timedelta
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MarketCap')
env = os.environ.get('env')

class Spider:
    def __init__(self):
        # self.cmc_url = 'https://coinmarketcap.com/'
        self.cmc_url = 'https://coinmarketcap.com/'
        self.mood_url = 'https://alternative.me/crypto/fear-and-greed-index/'
        self.mood_headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-encoding": "gzip",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "max-age=0",
                "cookie": os.getenv('COOKIE_KOL_INSIGHT', ''),
                "dnt": "1",
                "referer": "https://alternative.me/",
                "sec-ch-ua": "\"Chromium\";v=\"112\", \"Google Chrome\";v=\"112\", \"Not:A-Brand\";v=\"99\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"macOS\"",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }
        self.cmc_headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }
        self.redis_cli = redis_cli()
        self.web_hook_api = os.getenv('LARK_WEBHOOK_KOL_INSIGHT', '')


    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10
        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def req_cmc(self):
        """
        从cmc获取市场总市值和24小时交易量数据
        """
        # 结束时间
        timeEnd = int(time.time())
        # 开始时间
        now = datetime.now()
        # 获取当前时间减去1个月的时间
        last_month = now - timedelta(days=30)
        timeStart = int(time.mktime(last_month.timetuple()))
        url = f'https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/historical?format=chart&interval=1h&timeEnd={timeEnd}&timeStart={timeStart}'
        res = requests.get(url,headers=self.cmc_headers)
        logger.info(f'{res.status_code} {self.cmc_url}')
        data = res.json()
        totalMarketCap = data["data"]["quotes"][-1]["quote"][0]["totalMarketCap"]
        market_cap = int(totalMarketCap)
        totalVolume24H = data["data"]["quotes"][-1]["quote"][0]["totalVolume24H"]
        vol_24 = int(totalVolume24H)
        # 程序首次运行的时候 没有这个key，需要初始化
        if not self.redis_cli.get('cmc:market_cap'):
            logger.info('redis初始化 cmc')
            self.redis_cli.set('cmc:market_cap',market_cap)
            self.redis_cli.set('cmc:vol_24',vol_24)
        return market_cap,vol_24

    def get_mood(self):
        """
        获取市场情绪数据
        """
        res = requests.get(self.mood_url,headers=self.mood_headers)
        logger.info(f'{res.status_code} {self.mood_url}')
        tree = etree.HTML(res.text)
        now = tree.xpath('//div[contains(./text(),"Now")]/../following-sibling::*[1]/div/text()')[0]
        label_now = tree.xpath('//div[contains(./text(),"Now")]/following-sibling::*[1]/text()')[0]
        yesterday = tree.xpath('//div[contains(./text(),"Yesterday")]/../following-sibling::*[1]/div/text()')[0]
        label_yesterday = tree.xpath('//div[contains(./text(),"Yesterday")]/following-sibling::*[1]/text()')[0]
        return now,yesterday,label_now,label_yesterday

    def standard_content(self):
        # 今日数据
        market_cap,vol_24 = self.req_cmc()
        # 昨日数据
        old_market_cap = int(self.redis_cli.get('cmc:market_cap'))
        old_vol_24 = int(self.redis_cli.get('cmc:vol_24'))
        market_diff_amplitude = round(((market_cap - old_market_cap)/old_market_cap)*100,1)
        # 加密总市值增幅
        if market_diff_amplitude < 0:
            market_diff_amplitude_zh = f'相比昨天下跌 {abs(market_diff_amplitude)}%'
            market_diff_amplitude_en = f'down by {abs(market_diff_amplitude)}% in 24 hrs'
        else:
            market_diff_amplitude_zh = f'相比昨天上涨 {market_diff_amplitude}%'
            market_diff_amplitude_en = f'up by {market_diff_amplitude}% in 24 hrs'

        vol_24_diff_amplitude = round(((vol_24 - old_vol_24)/old_vol_24)*100,1)
        if vol_24_diff_amplitude < 0:
            vol_24_diff_amplitude_zh = f'相比昨天下跌 {abs(vol_24_diff_amplitude)}%'
            vol_24_diff_amplitude_en = f'down by {abs(vol_24_diff_amplitude)}% in 24 hrs'
        else:
            vol_24_diff_amplitude_zh = f'相比昨天上涨 {vol_24_diff_amplitude}%'
            vol_24_diff_amplitude_en = f'up by {vol_24_diff_amplitude}% in 24 hrs'
        # 存入当天数据，给明天的程序调用
        self.redis_cli.set('cmc:market_cap', market_cap)
        self.redis_cli.set('cmc:vol_24', vol_24)
        # 格式化数值   10亿为单位
        market_cap = f'{round(market_cap/1000000000,1):,}'
        vol_24 = f'{round(vol_24/1000000000,1):,}'
        old_market_cap = f'{int(old_market_cap/1000000000):,}'
        old_vol_24 = f'{round(old_vol_24/1000000000,1):,}'
        now_index,yesterday_index,label_now,label_yesterday = self.get_mood()
        # 给报警内容加入日期
        now = datetime.now(timezone.utc)
        tiem_zh = now.strftime('%m月%d日 %H')
        time_en = now.strftime('%b. %d, %H')
        content = f"""Crypto Market Trend
        截止{tiem_zh}:00 UTC：
        - 加密市场总市值 = {market_cap} Billion USD ( {market_diff_amplitude_zh}，昨日数据：{old_market_cap} Billion USD )
        - 24小时总交易量 = {vol_24} Billion USD ({vol_24_diff_amplitude_zh}，昨日数据：{old_vol_24} Billion USD ）
        - 市场情绪指数 = {now_index} {label_now}（昨日为 {yesterday_index}，{label_yesterday}） 
        市场分析：
        
        Crypto Market Trend
        Investigated  by {time_en}:00 UTC：
        - Total Market Cap = {market_cap} Billion USD ({market_diff_amplitude_en}, previous data: {old_market_cap} Billion USD)
        - 24 hrs Total Trading Vol. = {vol_24} Billion USD ({vol_24_diff_amplitude_en}, previous data: {old_vol_24} Billion USD)
        - Market Sentiment Index = {now_index} {label_now} (previously {yesterday_index}, {label_yesterday})
        """
        logger.info(content)
        sender(content,self.web_hook_api,title='Kol Insight')
        logger.info('推送成功')
        # 推送后记录，不在23小时推送
        self.redis_cli.setex('kol_insight:alertfilter', 2*60*60, 'alerted')

    def run(self):
        """
        每日10点调度一次
        """
        if env != 'prod':
            self.standard_content()
            return
        while True:
            # 给报警内容加入日期
            now = datetime.now(timezone.utc)
            time_H = now.strftime('%H')
            # 第一层控制在10点
            # 东八区早上10：00推送
            if time_H == '02':
                # 第二层控制防止在10点这一个小时内反复推送
                # 当日未推送过的再推
                if not self.redis_cli.get('kol_insight:alertfilter'):
                    self.standard_content()
                else:
                    logger.info('redis key 推送去重 23小时内不再推送，等待下次调度')
            else:
                logger.info('尚未到调度的时间')
            # 60s循环一次，看是否满足调度条件
            time.sleep(60)

