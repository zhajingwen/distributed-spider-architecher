import time
import json
import logging
import os
from functools import wraps
from traceback import format_exc
from math import ceil
from threading import Thread
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from .retry import retry_net

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 CoinList unisat_playwright.io')
env = os.environ.get('env')


class Spider:
    def __init__(self):
        self.base_url = 'https://unisat.io/brc20-api-v2/brc20/status?ticker=&start={}&limit=500&complete=&sort=minted'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.list_one_done = 'crawl-brc20:list1:done'
        self.list_two_done = 'crawl-brc20:list2:done'
        self.cookies_store = 'crawl-brc20:unisat_playwright:cookies'
        self.lark_url = os.getenv('LARK_WEBHOOK_BRC20', '')

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

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hold
        """
        while True:
            cookie_json = self.redis_cli.spop(self.cookies_store)
            if not cookie_json:
                logger.warning('当前没有可调用的cookies,等待...')
                time.sleep(5)
                continue
            cookie_dict = json.loads(cookie_json)
            # cookie超过有效期，那么久重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30 * 60:
                logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry()
    def req(self, num):
        """
        获取代币总量和总市值
        """
        url = self.base_url.format(num)
        # 获取cookie
        cookie_dict = self.get_cookie()
        # 以下三项均来自rpc
        self.headers['user-agent'] = cookie_dict['ua']
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        logger.info(f'request: {url}')
        res = retry_net(cookie_dict, url, self.headers, proxies)
        if not res:
            return
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        else:
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        data = res.json()['data']
        # logger.info(f'data: {data}')
        # 第一次进入，开启翻页模式
        pages = ceil(data['total'] / 500)
        if pages:
            # 识别首次进入
            if num == 0:
                logger.info(f'总页数：{pages}')
                for i in range(1, pages):
                    # 多线程翻页请求并解析入库
                    t = Thread(target=self.req, args=(i * 500,))
                    t.start()
                    # 由于上了cf 限制频率，免得打死了
                    time.sleep(10)
        start_time = int(time.time())
        update_query = 'UPDATE brc20_tokens SET mint_progress=%s,update_time=now()WHERE name=%s'
        update_data = []
        names = []
        detail = data['detail']
        for item in detail:
            name = item['ticker']
            name = name.lower()
            progress = (item['completeHeight'] / item['deployHeight']) * 100
            if progress > 100:
                progress = 100
            if progress < 1:
                progress = 0
            # 查看是否能关联
            status = self.redis_cli.sismember(self.list_one_done, name)
            # 能关联到则更新
            if status:
                update_one_data = (progress, name)
                update_data.append(update_one_data)
                names.append(name)
        if update_data:
            self.update_mysql_test(update_query, update_data, names)
        logger.info(f'page: {num} 耗时：{int(time.time()) - start_time} s')

    def update_mysql_test(self, update_query, update_data, names):
        """
        由于要算24H mint进度数据，故数据库24小时刷新一次
        """
        # 入库返回值
        status = self.rds.update_many(update_query, update_data)
        # 插入成功
        if status:
            # 将第二次列表页请求得到的数据补充到数据库后，对已经执行的记录到redis
            with self.redis_cli.pipeline(transaction=False) as pipe:
                for name in names:
                    pipe.sadd(self.list_two_done, name)
                pipe.execute()
                logger.info(f'update successfully {names}')
        else:
            logger.error(f'update failed {names}')


    def run(self):
        self.req(0)

if __name__ == '__main__':
    Spider().run()
