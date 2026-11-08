import schedule
import time
import os
import requests
import logging
from pytrends.request import TrendReq
from hashlib import md5
from traceback import format_exc
from datetime import datetime
from functools import wraps
from config import config
from utils.rds import DataUtils
# from utils.proxy_requests import proxies
from utils.lark_bot import sender
from .worldwide import insert_data_worldwide

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GOOGLE TRENDS')
env = os.environ.get('env')

countrys = {
    'South Korea': {'area': 'East Asia', 'geo': 'KR'},
    'Japan': {'area': 'East Asia', 'geo': 'JP'},
    'China': {'area': 'East Asia', 'geo': 'CN'},
    'Hongkong': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'HK'},
    'Macao': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'MO'},
    'Taiwan': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'TW'},
    'Vietnam': {'area': 'Southeast Asia', 'geo': 'VN'},
    'Thailand': {'area': 'Southeast Asia', 'geo': 'TH'},
    'Indonesia': {'area': 'Southeast Asia', 'geo': 'ID'},
    'Malaysia': {'area': 'Southeast Asia', 'geo': 'MY'},
    'Singapore': {'area': 'Southeast Asia', 'geo': 'SG'},
    'Myanmar': {'area': 'Southeast Asia', 'geo': 'MM'},
    'the Philippines': {'area': 'Southeast Asia', 'geo': 'PH'},
    'Cambodia': {'area': 'Southeast Asia', 'geo': 'KH'}, 'India': {'area': 'South Asia', 'geo': 'IN'},
    'Pakistan': {'area': 'South Asia', 'geo': 'PK'},
    'United States': {'area': 'English area', 'geo': 'US'}, 'U.K.': {'area': 'English area', 'geo': 'GB'},
    'Canada': {'area': 'English area', 'geo': 'CA'}, 'Australia': {'area': 'English area', 'geo': 'AU'},
    'Russia': {'area': 'CIS area', 'geo': 'RU'}, 'Ukraine': {'area': 'CIS area', 'geo': 'UA'},
    'Belarus': {'area': 'CIS area', 'geo': 'BY'}, 'Kazakhstan': {'area': 'CIS area', 'geo': 'KZ'},
    'Uzbekistan': {'area': 'CIS area', 'geo': 'UZ'}, 'Turkey': {'area': 'European region', 'geo': 'TR'},
    'Germany': {'area': 'European region', 'geo': 'DE'},
    'France': {'area': 'European region', 'geo': 'FR'}, 'Italy': {'area': 'European region', 'geo': 'IT'},
    'Spain': {'area': 'European region', 'geo': 'ES'},
    'Netherlands': {'area': 'European region', 'geo': 'NL'},
    'Switzerland': {'area': 'European region', 'geo': 'CH'},
    'Poland': {'area': 'European region', 'geo': 'PL'},
    'Belgium': {'area': 'European region', 'geo': 'BE'},
    'united arab emirates': {'area': 'Middle East', 'geo': 'AE'},
    'Saudi Arabia': {'area': 'Middle East', 'geo': 'SA'}, 'Qatar': {'area': 'Middle East', 'geo': 'QA'},
    'Israel': {'area': 'Middle East', 'geo': 'IL'},
    'Argentina': {'area': 'latin america region', 'geo': 'AR'},
    'Brazil': {'area': 'latin america region', 'geo': 'BR'},
    'Mexico': {'area': 'latin america region', 'geo': 'MX'},
    'Uruguay': {'area': 'latin america region', 'geo': 'UY'},
    'Chile': {'area': 'latin america region', 'geo': 'CL'},
    'Colombia': {'area': 'latin america region', 'geo': 'CO'},
    'nigeria': {'area': 'African region', 'geo': 'NG'},
    'South Africa': {'area': 'African region', 'geo': 'ZA'},
    'Egypt': {'area': 'African region', 'geo': 'EG'},
    'morocco': {'area': 'African region', 'geo': 'MA'},
    'Algeria': {'area': 'African region', 'geo': 'DZ'},
    'worldwide': {'area': '', 'geo': ''}
    }
web_hook = os.getenv('LARK_WEBHOOK_GOOGLETRENDS', '')

class Search:
    def __init__(self):
        self.proxy_url = config.PROXY_URL
        self.rds = DataUtils('spider')
        self.table = 'google_trends2'
        self.translate_url = 'https://translate.googleapis.com/translate_a/single?client=gtx&tl=en&sl=auto&dt=t&q={}'
        self.headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }

    def proxy(self):
        """
        luminati代理
        """
        proxies = [self.proxy_url]
        return proxies

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
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
                        if 'Proxy Error' in format_exc():
                            logger.warning('Proxy Err')
                        elif 'ProxyError' in format_exc():
                            logger.warning('Proxy Err')
                        elif 'SSLEOFError' in format_exc():
                            logger.warning('SSLEOFErr')
                        elif 'timed out' in format_exc():
                            logger.warning('timed out')
                        elif '451 Client Error:' in format_exc():
                            logger.warning('451 Client Err')
                        else:
                            logger.warning(format_exc())
                        retry_num += 1
                        content = f"""
                                               国家：{args[-3]}
                                               区域：{countrys[args[-3]]}
                                               """
                        if retry_num > num:
                            logger.error(f'{args[-3]} 重试超过次数')
                            sender(f'{content}',web_hook,'失败')
                            break
                        logger.warning(f'重试 {retry_num}: {content}')
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    # @retry(5)
    # def translate(self, keyword):
    #     url = self.translate_url.format(keyword)
    #     res = requests.get(url,headers=self.headers,proxies=proxies)
    #     translation_c = res.json()[0][0][0]
    #     return translation_c

    @retry(5)
    def req(self, country="美国", spider_time=1111, spider_date='None'):
        """
        调用接口发请求拿到数据
        return: dict 数据样例参考one_kw_search3api
        """
        session = requests.Session()
        session.get('https://trends.google.com')
        cookies_map = session.cookies.get_dict()
        nid_cookie = cookies_map['NID']
        # 创建链接
        # hl:语言
        # tz:谷歌自定义的时区的概念，不是通行标准 360表示美国的时区
        # backoff_factor：退避因子，可以理解为重试时间间隔的分布粒度。比如0.1表示在0.1-xxx,之间随机调用sleep时间，来过风控。但是如果用代理的话是用不着的默认是禁用的，不用传参
        pytrends = TrendReq(
            hl='en-US', tz=360, timeout=(10,25), proxies=self.proxy(),
            retries=3, requests_args=None
        )
        # 关键词列表
        word = 'Crypto'
        kw_list = [word]
        # cat是catgory的意思，可以指定类目ID，默认为不指定（0表示不指定）
        # timeframe表示查询时间和查询粒度点意思，比如today 5-y表示最近5年，支持小时，天，月，年的查询粒度
        # geo更为细致的地理位置指定，比如州，省，县之类的 US  默认是全球
        # gprop指定搜索属性：比如你只想看图片的搜索'images'，默认为网络搜索
        geo = countrys[country]['geo']
        area = countrys[country]['area']
        pytrends.build_payload(kw_list, cat=0, timeframe='now 1-d', geo=geo, gprop='')
        # 该字段就是拿到指数走势的接口
        all_update_sql_base = "replace into {}(id,geo,country,area,related_words,spider_time,spider_date) values{};"
        sql_values = []
        ori_data = pytrends.related_queries()
        if 'default' not in ori_data:
            logger.info(f'该关键词 Crypto 在 该区域 {geo} {area} 无数据')
            return
        data = ori_data['default']['rankedList'][1]['rankedKeyword']
        # 解析落库全球的数据
        if geo == '':
            status = insert_data_worldwide(data, spider_date, self.rds, spider_time)
            if not status:
                logger.info(f'worldwide 请求成功，但是数据为空 {ori_data}')
            return
        for d in data:
            related_words = d['query']
            # tranlate the word to english
            # related_words = self.translate(related_words)
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
            logger.info(f'{country} {spider_date} 请求成功，但是数据为空 {ori_data}')
            id = md5(f'{country}{spider_time}'.encode('utf-8')).hexdigest()
            update_sql = f"({repr(id)},{repr(geo)},{repr(country)},{repr(area)},'',{spider_time},{repr(spider_date)})"
            sql_values.append(update_sql)
        if sql_values:
            # 多条记录一次性插入
            all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
            self.rds.insert(all_update_sql)

    def all_country(self):
        """
        采集所有国家
        """
        spider_time = int(time.time())
        spider_date = datetime.now().strftime("%Y-%m-%d")
        for c in countrys:
            # if c != 'worldwide':
            #     continue
            logger.info(f'开始采集：{c} {spider_date}')
            self.req(c, spider_time, spider_date)

    def run(self):
        """
        启动入口 定时调度
        """
        if env != 'prod':
            self.all_country()
        else:
            logger.info(f'程序启动，等待调度中...')
            # 每天5：20 启动
            schedule.every().day.at("05:20").do(self.all_country)
            while True:
                schedule.run_pending()
                time.sleep(1)
        # if env != 'prod':
        #     self.all_country()
        # else:
        #     logger.info(f'程序启动，等待调度中...')
        #     while True:
        #         # 每日6：00 - 8：10为可执行时间区间，拉长可执行时间可以避免容器异常时恰好卡在了调度时间区间内，导致无法正常调度
        #         today_now = datetime.now()
        #         today_at_06_00 = today_now.replace(hour=6, minute=0, second=0)
        #         today_at_08_10 = today_now.replace(hour=8, minute=10, second=0)
        #         if today_at_06_00 < today_now < today_at_08_10:
        #             logger.info('激活调度')
        #             self.all_country()
        #             logger.info('调度结束')
        #             time.sleep(60 * 60)
        #         time.sleep(10)
