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
from utils.proxy_requests import proxies
from utils.lark_bot import sender
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GOOGLE TRENDS')
env = os.environ.get('env')

web_hook = os.getenv('LARK_WEBHOOK_GOOGLETRENDS', '')

class Search:
    def __init__(self):
        # self.proxy_url = "<PROXY_URL>"
        self.proxy_url = config.PROXY_URL
        # self.proxy_url = 'http://<GOOGLETRENDS_PROXY>'
        # self.countrys = {'韩国': {'area': '东亚区域', 'geo': 'KR'}, '日本': {'area': '东亚区域', 'geo': 'JP'}, '中国': {'area': '东亚区域', 'geo': 'CN'}, '香港': {'area': '港澳台区域', 'geo': 'HK'}, '澳门': {'area': '港澳台区域', 'geo': 'MO'}, '台湾': {'area': '港澳台区域', 'geo': 'TW'}, '越南': {'area': '东南亚区域', 'geo': 'VN'}, '泰国': {'area': '东南亚区域', 'geo': 'TH'}, '印度尼西亚': {'area': '东南亚区域', 'geo': 'ID'}, '马来西亚': {'area': '东南亚区域', 'geo': 'MY'}, '新加坡': {'area': '东南亚区域', 'geo': 'SG'}, '缅甸': {'area': '东南亚区域', 'geo': 'MM'}, '菲律宾': {'area': '东南亚区域', 'geo': 'PH'}, '柬埔寨': {'area': '东南亚区域', 'geo': 'KH'}, '印度': {'area': '南亚区域', 'geo': 'IN'}, '巴基斯坦': {'area': '南亚区域', 'geo': 'PK'}, '美国': {'area': '英文区域', 'geo': 'US'}, '英国': {'area': '英文区域', 'geo': 'GB'}, '加拿大': {'area': '英文区域', 'geo': 'CA'}, '澳大利亚': {'area': '英文区域', 'geo': 'AU'}, '俄罗斯': {'area': 'CIS区域', 'geo': 'RU'}, '乌克兰': {'area': 'CIS区域', 'geo': 'UA'}, '白俄罗斯': {'area': 'CIS区域', 'geo': 'BY'}, '哈萨克斯坦': {'area': 'CIS区域', 'geo': 'KZ'}, '乌兹别克斯坦': {'area': 'CIS区域', 'geo': 'UZ'}, '土耳其': {'area': '欧洲区域', 'geo': 'TR'}, '德国': {'area': '欧洲区域', 'geo': 'DE'}, '法国': {'area': '欧洲区域', 'geo': 'FR'}, '意大利': {'area': '欧洲区域', 'geo': 'IT'}, '西班牙': {'area': '欧洲区域', 'geo': 'ES'}, '荷兰': {'area': '欧洲区域', 'geo': 'NL'}, '瑞士': {'area': '欧洲区域', 'geo': 'CH'}, '波兰': {'area': '欧洲区域', 'geo': 'PL'}, '比利时': {'area': '欧洲区域', 'geo': 'BE'}, '阿拉伯联合酋长国': {'area': '中东区域', 'geo': 'AE'}, '沙特阿拉伯': {'area': '中东区域', 'geo': 'SA'}, '卡塔尔': {'area': '中东区域', 'geo': 'QA'}, '以色列': {'area': '中东区域', 'geo': 'IL'}, '阿根廷': {'area': '拉丁美洲区域', 'geo': 'AR'}, '巴西': {'area': '拉丁美洲区域', 'geo': 'BR'}, '墨西哥': {'area': '拉丁美洲区域', 'geo': 'MX'}, '乌拉圭': {'area': '拉丁美洲区域', 'geo': 'UY'}, '智利': {'area': '拉丁美洲区域', 'geo': 'CL'}, '哥伦比亚': {'area': '拉丁美洲区域', 'geo': 'CO'}, '尼日利亚': {'area': '非洲区域', 'geo': 'NG'}, '南非': {'area': '非洲区域', 'geo': 'ZA'}, '埃及': {'area': '非洲区域', 'geo': 'EG'}, '摩洛哥': {'area': '非洲区域', 'geo': 'MA'}, '阿尔及利亚': {'area': '非洲区域', 'geo': 'DZ'}}
        self.countrys = {'South Korea': {'area': 'East Asia', 'geo': 'KR'}, 'Japan': {'area': 'East Asia', 'geo': 'JP'}, 'China': {'area': 'East Asia', 'geo': 'CN'}, 'Hongkong': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'HK'}, 'Macao': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'MO'}, 'Taiwan': {'area': 'Hong Kong, Macao and Taiwan regions', 'geo': 'TW'}, 'Vietnam': {'area': 'Southeast Asia', 'geo': 'VN'}, 'Thailand': {'area': 'Southeast Asia', 'geo': 'TH'}, 'Indonesia': {'area': 'Southeast Asia', 'geo': 'ID'}, 'Malaysia': {'area': 'Southeast Asia', 'geo': 'MY'}, 'Singapore': {'area': 'Southeast Asia', 'geo': 'SG'}, 'Myanmar': {'area': 'Southeast Asia', 'geo': 'MM'}, 'the Philippines': {'area': 'Southeast Asia', 'geo': 'PH'}, 'Cambodia': {'area': 'Southeast Asia', 'geo': 'KH'}, 'India': {'area': 'South Asia', 'geo': 'IN'}, 'Pakistan': {'area': 'South Asia', 'geo': 'PK'}, 'United States': {'area': 'English area', 'geo': 'US'}, 'U.K.': {'area': 'English area', 'geo': 'GB'}, 'Canada': {'area': 'English area', 'geo': 'CA'}, 'Australia': {'area': 'English area', 'geo': 'AU'}, 'Russia': {'area': 'CIS area', 'geo': 'RU'}, 'Ukraine': {'area': 'CIS area', 'geo': 'UA'}, 'Belarus': {'area': 'CIS area', 'geo': 'BY'}, 'Kazakhstan': {'area': 'CIS area', 'geo': 'KZ'}, 'Uzbekistan': {'area': 'CIS area', 'geo': 'UZ'}, 'Turkey': {'area': 'European region', 'geo': 'TR'}, 'Germany': {'area': 'European region', 'geo': 'DE'}, 'France': {'area': 'European region', 'geo': 'FR'}, 'Italy': {'area': 'European region', 'geo': 'IT'}, 'Spain': {'area': 'European region', 'geo': 'ES'}, 'Netherlands': {'area': 'European region', 'geo': 'NL'}, 'Switzerland': {'area': 'European region', 'geo': 'CH'}, 'Poland': {'area': 'European region', 'geo': 'PL'}, 'Belgium': {'area': 'European region', 'geo': 'BE'}, 'united arab emirates': {'area': 'Middle East', 'geo': 'AE'}, 'Saudi Arabia': {'area': 'Middle East', 'geo': 'SA'}, 'Qatar': {'area': 'Middle East', 'geo': 'QA'}, 'Israel': {'area': 'Middle East', 'geo': 'IL'}, 'Argentina': {'area': 'latin america region', 'geo': 'AR'}, 'Brazil': {'area': 'latin america region', 'geo': 'BR'}, 'Mexico': {'area': 'latin america region', 'geo': 'MX'}, 'Uruguay': {'area': 'latin america region', 'geo': 'UY'}, 'Chile': {'area': 'latin america region', 'geo': 'CL'}, 'Colombia': {'area': 'latin america region', 'geo': 'CO'}, 'nigeria': {'area': 'African region', 'geo': 'NG'}, 'South Africa': {'area': 'African region', 'geo': 'ZA'}, 'Egypt': {'area': 'African region', 'geo': 'EG'}, 'morocco': {'area': 'African region', 'geo': 'MA'}, 'Algeria': {'area': 'African region', 'geo': 'DZ'}}
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

    # @retry(5)
    # def translate(self, keyword):
    #     url = self.translate_url.format(keyword)
    #     res = requests.get(url,headers=self.headers,proxies=proxies)
    #     translation_c = res.json()[0][0][0]
    #     return translation_c

    @retry()
    def req(self, country="美国"):
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
        # cookies = '__utmc=10102256; __utma=10102256.262768926.1705310974.1705454812.1705488572.4; __utmz=10102256.1705488572.4.3.utmcsr=trends.google.com|utmccn=(referral)|utmcmd=referral|utmcct=/; __utmt=1; __utmb=10102256.7.9.1705488598409; SSID=Agg7xJBw1YzdBIzol; HSID=AnXt10Bfz1XsKs96R; APISID=g7xihozEsncFDMtd/A6MYq7dtXRZtYxK4l; SAPISID=TiWbFQaHqAgKD0xa/ASmqmqcbLVnT0jQCw; __Secure-1PAPISID=TiWbFQaHqAgKD0xa/ASmqmqcbLVnT0jQCw; __Secure-3PAPISID=TiWbFQaHqAgKD0xa/ASmqmqcbLVnT0jQCw; __Secure-ENID=16.SE=ZZ01iZZtItF0aY8hn4iIrJNx8tju5T_WVi6_Np6quN5Coeol2b5ZwKx-R-DCt0XbtEXzNw6vImNvMrNySztAO8X8soKv6Pnvqqs8oanx3zbOk0baE_F-ksvFgm3YmejuVzETaI6_fgvecchJWQVII0MnZHSSbwZ0wX6ojAzrsmBIlu2DKw7gF4IewqY16txy6vrnnw6IbPjiTqKVj3njfqIhCBfReqNWQ9SjKTTI2BgrwcecPrMTz1O6G3HCPSfFXtdlHUPcBO1CB8caxxDotLnYd58fuR83uRoETHjyvQVm2PlnSL7nss2_OD_fC4ACh6FjlPCvANNmXYdxwCOBvOfKcXjqMQSBs-4AijVk1Xg; S=billing-ui-v3=exhg9ajYkz5nLFz9yd_TIvXaBGZqo6lt:billing-ui-v3-efe=exhg9ajYkz5nLFz9yd_TIvXaBGZqo6lt; SID=fQjds6Fw2s3GzCQ_LJg8s3QCvzox6Esu7d3Gjnuddo3raliVc25ERVYXNxrTo8bwYgdBUg.; __Secure-1PSID=fQjds6Fw2s3GzCQ_LJg8s3QCvzox6Esu7d3Gjnuddo3raliVFP-q9x3X1_WJcrlZKGZn_g.; __Secure-3PSID=fQjds6Fw2s3GzCQ_LJg8s3QCvzox6Esu7d3Gjnuddo3raliV5Yrfi-nZuH4ZiOYFFztIiw.; OTZ=7383450_24_24__24_; _gid=GA1.3.397583576.1705449516; AEC=Ae3NU9OlE9LZqoUNHNYPTzrmBg9LUC9untLqQWuxVHR2QbtjisehiA60HQ; NID=511=um5Uc6qsI8X2JAdDC6OQ8Yv_TnYWujUBrkxn-e9HVItDdne4xNElkf51f2KB-Bke7_pMgVvaTqCI8sh1hwFiicWbPLJVQEVTyhUMERt5S83WvFF5SmPUNgQjADsuzrKAafRnlDQlw61XMBT5lzxxc7Ml7mwfHsNAg-UUoe55YC_Ze4AoBymErk2M8a6fPeLeULu883gDvmcgOeIKwds4AwGarNlpYDnAj8Uev0MYylgSFkkvwa7t96ZV0tPudxDgmAWbMv4yHGAlpbNYlnSw6UlNzl3s6YL_A8fxTyydcN0_NyPTLo8NIWPNaEPtPvTl5R3AutmFHe5UPAo-E13zDO9tdHLrsQ33BJNwqwYhpX3ndZAtl7nvtha46zlr9XsphLZEtNYgP7OIjiTasccawwUK6tNQxnGdtPNsSavFafI9pfLuWbrvK9LfGjmi6tpACZBvV5q8lYKmjL6E6vtb2ukGfqdWyx86S4R0XHukE1_rqhira8wfXq5lOl0NZtnTfAuLt0ODKV_dMOzsiw0zeGwaY6o; __Secure-1PSIDTS=sidts-CjIBPVxjSlnpjiF-4IXlCNcioJZOQDBr7GCdpiEEvgBLtxQjiig9mlGgTVklAReZR7yYYRAA; __Secure-3PSIDTS=sidts-CjIBPVxjSlnpjiF-4IXlCNcioJZOQDBr7GCdpiEEvgBLtxQjiig9mlGgTVklAReZR7yYYRAA; 1P_JAR=2024-01-17-10; _gat_gtag_UA_4401283=1; _ga=GA1.3.262768926.1705310974; _ga_VWZPXDNJJB=GS1.1.1705488553.6.1.1705488601.0.0.0; SIDCC=ABTWhQFVGJGXovaItpApNwvmITbWySI5WqWWj7StRLHNXbav0NRzTo6Jdh7rIMqXYYFyHdjR8-0; __Secure-1PSIDCC=ABTWhQF7e-v4KWfhL2fe0PxegCAN1U0QBbieXPbWj-kYH5Tg67HXopCwiYc_5P_0nLBJC3PSGtc; __Secure-3PSIDCC=ABTWhQEod8bMH7oGy3xeuuAQQHfg4lbGQvJWa9C8Bax_QFapBEg4jReUNSwl7eojl0fp7veZCik'
        # pytrends = TrendReq(
        #     hl='en-US', tz=360, timeout=(10, 25),
        #     retries=3, requests_args={'headers': {'Cookie': cookies}}
        # )
        # 构建搜索对象
        # 关键词列表
        word = 'Crypto'
        kw_list = [word]
        # cat是catgory的意思，可以指定类目ID，默认为不指定（0表示不指定）
        # timeframe表示查询时间和查询粒度点意思，比如today 5-y表示最近5年，支持小时，天，月，年的查询粒度
        # geo更为细致的地理位置指定，比如州，省，县之类的 US  默认是全球
        # gprop指定搜索属性：比如你只想看图片的搜索'images'，默认为网络搜索
        geo = self.countrys[country]['geo']
        area = self.countrys[country]['area']
        pytrends.build_payload(kw_list, cat=0, timeframe='today 3-m', geo=geo, gprop='')
        # 该字段就是拿到指数走势的接口
        # all_update_sql_base = "replace into {}(id,geo,country,area,related_words,spider_time,spider_date) values{};"
        # sql_values = []
        ori_data = pytrends.related_queries()
        if 'default' not in ori_data:
            logger.info(f'该关键词 Crypto 在 该区域 {geo} {area} 无数据')
            return
        data = ori_data['default']['rankedList'][1]['rankedKeyword']
        print(data)

    def all_country(self):
        """
        采集所有国家
        """
        # spider_time = int(time.time())
        # spider_date = datetime.now().strftime("%Y-%m-%d")
        for c_name in self.countrys:
            # self.req(c,spider_time)
            # if c == 'United States':
            logger.info(f'开始采集：{c_name}')
            self.req(c_name)

    def run(self):
        """
        启动入口 定时调度
        """
        self.all_country()