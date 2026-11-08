import logging
import time
import requests
from functools import wraps
from traceback import format_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('REQUEST RETRY')

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
                    break
                except:
                    logger.warning(f'{func.__name__}网络请求失败，重试{retry_num}...')
                    if 'Proxy Error' in format_exc():
                        logger.warning('Proxy Err')
                    elif 'ProxyError' in format_exc():
                        logger.warning('Proxy Err')
                    elif 'SSLEOFError' in format_exc():
                        logger.warning('SSLEOFErr')
                    elif 'OSError' in format_exc():
                        logger.warning('OSError')
                    elif 'ProtocolError' in format_exc():
                        logger.warning('ProtocolError')
                    elif 'timed out' in format_exc():
                        logger.warning('timed out')
                    elif '451 Client Error:' in format_exc():
                        logger.warning('451 Client Err')
                    elif 'RetryError' in format_exc():
                        logger.warning('RetryErr')
                    else:
                        logger.info(format_exc())
                    retry_num += 1
                    if retry_num > num:
                        logger.warning(f'重试超过次数{retry_num}')
                        break
                    # 重试依旧是等待3s，否则会把账号打废掉
                    time.sleep(3)
            return res

        return wrapper

    return recive_func

def retry_net(cookie_dict, url, headers, proxies):
    num = 0
    while True:
        num += 1
        try:
            if 'cf' in cookie_dict:
                cookies = {
                    'cf_clearance': cookie_dict['cf']
                }
                res = requests.get(url, headers=headers, proxies=proxies, cookies=cookies)
            else:
                res = requests.get(url, headers=headers, proxies=proxies)
            logger.info(f'response code: {res.status_code} {url}')
            return res
        except:
            time.sleep(1)
            if num > 3:
                logger.warning(f'网络错误：{url} {proxies} {format_exc()}')
                return None
