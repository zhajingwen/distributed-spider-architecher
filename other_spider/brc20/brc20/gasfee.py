import requests
import time
import logging
from functools import wraps
from traceback import format_exc
from utils.proxy_requests import proxies
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 Overview')


class Spider:
    def __init__(self):
        self.url = 'https://mempool.space/api/v1/fees/recommended'
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
        logger.info(f'request: {self.url}')
        res = requests.get(self.url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {self.url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')

        data = res.json()
        if not data:
            return
        logger.info(data)
        fastestFee = data['fastestFee']
        halfHourFee = data['halfHourFee']
        hourFee = data['hourFee']
        economyFee = data['economyFee']
        sql = f'replace into brc20_gasfee(id,fast,middle,slow,economy,update_time)' \
              f' values("gasfee",{fastestFee},{halfHourFee},{hourFee},{economyFee},{int(time.time())})'
        self.rds.insert(sql)

    def run(self):
        while True:
            self.get_statistic1()
            # 每分钟刷新一次
            time.sleep(1*60)



if __name__ == '__main__':
    Spider().run()
