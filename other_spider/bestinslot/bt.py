import requests
import time
import schedule
import os
import logging
from functools import wraps
from traceback import format_exc
from threading import Thread
from utils.proxy_requests import proxies
from utils.rds import DataUtils
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Bestinslot')
env = os.environ.get('env')

class Spider:
    def __init__(self):
        # 24小时数据
        # https://v2api.bestinslot.xyz/brc20/all?page=1
        # https://ordapi.bestinslot.xyz/v1/get_brc20_tickers_info/7/{}
        # self.base_url = 'https://ordapi.bestinslot.xyz/v1/get_brc20_tickers_info/7/{}'
        self.base_url = 'https://v2api.bestinslot.xyz/brc20/all?page={}'
        self.headers = {
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.list_two_done = 'crawl-brc20:list2:done'
        self.bestinslot_done = 'crawl-brc20:bestinslot:done'

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
                            print(error)
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
    def req(self,num, btc_price):
        """
        获取代币总量和总市值
        """
        url = self.base_url.format(num)
        logger.info(f'request: {url}')
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        data = res.json()
        # 第一次进入，开启翻页模式
        last_page = data['last_page']
        per_page = data['per_page']
        pages = int(last_page/per_page)
        if pages:
            # 识别首次进入
            if num == 1:
                # 正常1289页
                logger.info(f'总页数：{pages}')
                for i in range(2,pages+1):
                    # 多线程翻页请求并解析入库
                    t = Thread(target=self.req,args=(i, btc_price,))
                    t.start()
                    # 控制并发数
                    time.sleep(1)
        start_time = int(time.time())
        insert_sql_list = []
        insert_sql_allbase = 'replace into bestinslot2 values{};'
        items = data['items']
        for item in items:
            name = item['tick']
            name = name.lower()
            # 匹配成功计数
            if self.redis_cli.sismember(self.list_two_done,name.replace('$','')):
                # 只计数一次
                if not self.redis_cli.sismember(self.bestinslot_done,name.replace('$','')):
                    self.redis_cli.incr('bestinslot')
                    self.redis_cli.sadd(self.bestinslot_done,name.replace('$',''))
            price = item.get('minlistedunitprice')
            if price:
                price = round(price*btc_price/100000000,2)
            else:
                price = 'null'
            market_cap = item['market_cap']
            if not market_cap:
                market_cap = 'null'
            else:
                market_cap = int(market_cap*btc_price/100000000)
            holders = item['holder_count']
            vol_24H = item.get('volume')
            if vol_24H:
                vol_24H = vol_24H.get('d1')
                vol_24H = int(vol_24H*btc_price/100000000)
            # vol_24H_change = item['change_24h']
            # if vol_24H_change:
            #     vol_24H_change = vol_24H_change/100
            # else:
            #     vol_24H_change = 'null'
            vol_24H_change = 'null'
            valid_txs = item['tx_count']
            supply = item.get('supply')
            if supply:
                listed_supply_ratio = supply.get('listed_ratio', 'null')
            else:
                listed_supply_ratio = 'null'
            update_time = int(time.time())
            insert_sql = f'({repr(name)},{price},{market_cap},{holders},{vol_24H},{vol_24H_change},{valid_txs},{listed_supply_ratio},{update_time})'
            insert_sql_list.append(insert_sql)
        if insert_sql_list:
            insert_sqls = insert_sql_allbase.format(','.join(insert_sql_list))
            status = self.rds.insert(insert_sqls)
            if status:
                logger.info(f'插入成功 {insert_sqls.split("into")[0]} into')
        logger.info(f'page: {num} 耗时：{int(time.time())-start_time} s')

    @retry()
    def btc_price(self):
        # https://v2api.bestinslot.xyz/sync
        # https://ordapi.bestinslot.xyz/v1/btc_price
        # url = 'https://ordapi.bestinslot.xyz/v1/btc_price'
        url = 'https://v2api.bestinslot.xyz/sync'
        # url = self.base_url.format(num)
        logger.info(f'request: {url}')
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        btc_price = res.json()['btc_price']
        return btc_price

    def job(self):
        btc_price = self.btc_price()
        self.req(1, btc_price)

    def run(self):
        """
        启动入口 定时调度
        """
        # 测试
        if env == 'test':
            self.job()
        else:
            # 每天7：00 启动
            schedule.every().day.at("07:00").do(self.job)
            while True:
                schedule.run_pending()
                time.sleep(1)
                # 10分钟一条日志
                if int(time.time())%600 == 0:
                    logger.info('等待调度中...')

if __name__ == '__main__':
    Spider().run()
