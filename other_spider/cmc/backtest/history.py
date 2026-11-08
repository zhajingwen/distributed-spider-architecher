import os
# import os
import json
import time
import requests
import logging
from traceback import format_exc
from functools import wraps
from utils.rds import DataUtils
# import pandas as pd
# # 设置你的代理
# os.environ["http_proxy"] = "http://127.0.0.1:1001"
# os.environ["https_proxy"] = "http://127.0.0.1:1001"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Back Test')


class GenCurrency:
    """
    据说只能取到2010/7/16之后的数据
    """
    def __init__(self):
        self.rds = DataUtils('spider')


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

    # 重试3次
    @retry(3)
    def fetch_ohlcv(self,fsym,tsym,limit,toTs,api_key=None):
        url = f"https://min-api.cryptocompare.com/data/v2/histominute?fsym={fsym}&tsym={tsym}&limit={limit}&toTs={toTs}&api_key={api_key}"
        response = requests.get(url)
        json_content = json.loads(response.content)
        data = json_content["Data"]["Data"]	# 转化为json格式
        # df = pd.DataFrame(data,columns=["time","high","low","open","close","volumefrom"])
        return data

    def time_interval(self):
        """
        获取所有历史数据，插入数据库
        """
        end_time = int(time.time())
        api_key = os.getenv('CMC_BACKTEST_API_KEY', '')
        num = 0
        while True:
            num += 1
            df = self.fetch_ohlcv("BTC","USD","2000",end_time,api_key)
            end_time = df[0]['time']
            base_sql = "replace into cmc_backtest_btc values {};"
            sqls = []
            for i in df:
                i.pop('conversionType')
                i.pop('conversionSymbol')
                timestamp = i['time']
                i.pop('time')
                value = json.dumps(i)
                sql = f"({timestamp},{repr(value)})"
                sqls.append(sql)
            long_sql = base_sql.format(','.join(sqls))
            # time.sleep(1)
            self.rds.insert(long_sql)
            content = f'{num} {len(df)} {df[0]} {df[-1]} 插入成功'
            logger.info(content)
            if len(df) < 2001:
                logger.info(f'数据跑完了，截止：{end_time}')
                break
