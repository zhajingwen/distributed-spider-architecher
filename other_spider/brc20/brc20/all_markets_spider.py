import requests
import time
import re
import logging
from lxml import etree
from functools import wraps
from traceback import format_exc
from utils.proxy_requests import proxies
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 Overview')


class Spider:
    def __init__(self):
        self.statistic_url = 'https://brc-20.io/'
        self.statistic_url_2 = 'https://brc-20.io/volume_iframe'
        self.headers = {
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()

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
    def get_statistic1(self):
        """
        获取代币总量和总市值
        """
        logger.info(f'request: {self.statistic_url}')
        res = requests.get(self.statistic_url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {self.statistic_url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        # total_market_cap = "total_mcap.innerHTML = 'Total Market Cap: $(\d{1,3}(,\d{3})*(\.\d{1,2})*)';"
        total_market_cap_pattern = "Total Market Cap: \$(\d{1,3}(,\d{3})*(\.\d{1,2})*)"
        match_ = re.search(total_market_cap_pattern,res.text)
        if match_:
            total_market_cap = match_.group(1)
            total_market_cap = total_market_cap.replace(',','')
        else:
            raise Exception('总市值获取失败')
            # logger.warning('总市值获取失败')
            # return
        tree = etree.HTML(res.text)
        total_supply = tree.xpath('//h5[contains(./text(),"total")]/text()')[0]
        if total_supply:
            total_supply = total_supply.replace(' total','').replace(',','')
        else:
            raise Exception('代币总数获取失败')
            # logger.warning('代币总数获取失败')
            # return
        volume = self.get_statistic2()
        logger.info(f'total_market_cap: {total_market_cap} total_supply: {total_supply} volume: {volume}')
        sql = f'replace into brc20_token_info(id,total_value,total_trans_amount,total_supply,update_time)' \
              f' values("overview",{repr(total_market_cap)},{repr(volume)},{repr(total_supply)},{int(time.time())})'
        self.rds.insert(sql)

    @retry()
    def get_statistic2(self):
        """
        获取Volume last 24 hours:
        """
        logger.info(f'request: {self.statistic_url_2}')
        res = requests.get(self.statistic_url_2,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {self.statistic_url_2}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        volume_pattern = "\$(\d{1,3}(,\d{3})*(\.\d{1,2})*)"
        match_ = re.search(volume_pattern,res.text)
        if match_:
            volume = match_.group(1)
            volume = volume.replace(',','')
            return volume
        else:
            raise Exception('代币总数获取失败')
            # logger.warning('24成交量获取失败')
            # return
    def run(self):
        while True:
            self.get_statistic1()
            # 每分钟刷新一次
            time.sleep(1*60)



if __name__ == '__main__':
    Spider().run()
