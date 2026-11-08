import requests
import time
import re
import datetime
import logging
from lxml import etree
from functools import wraps
from hashlib import md5
from traceback import format_exc
from threading import Thread
from utils.proxy_requests import proxies
from utils.rds import DataUtils
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 CoinMarkets')


class Spider:
    def __init__(self):
        """
        24小时刷新一次
        """
        self.base_url = 'https://brc-20.io/token?n={}'
        self.headers = {
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        # self.list_one_done = 'crawl-brc20:list1:done'
        # self.list_two_done = 'crawl-brc20:list2:done'
        self.markets_jobs = 'crawl-brc20:marketsjobs'
        # 无交易所信息黑名单
        self.markets_blacklist = 'crawl-brc20:marketsblacklist'
        self.markets_jobs_done = 'crawl-brc20:marketsjobsdone'
        self.history_prices_done = 'crawl-brc20:historypricesdone'

        # self.price_history_jobs = 'crawl-brc20:pricehistoryjobs'


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
    def req(self, name):
        """
        获取代币总量和总市值
        """
        url = self.base_url.format(name)
        logger.info(f'request: {url}')
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        try:
            # 采集历史价格数据
            self.history_prices(name, res.text)
        except:
            logger.warning(f'{name} 该币无历史价格信息')
            # 加入黑名单
            self.redis_cli.sadd(self.markets_blacklist, name)
            return
        tree = etree.HTML(res.text)
        patterns = tree.xpath('//table[@dir="ltr"]/tr')
        sql_base = 'replace into brc20_token_markets values {};'
        sqls = []
        for pattern in patterns:
            try:
                source = pattern.xpath('./td[2]/text()')[0].strip()
                pair = pattern.xpath('./td[3]/a/text()')[0].strip()
                price = pattern.xpath('./td[4]/text()')[0].strip()
                volume = pattern.xpath('./td[5]/text()')[0].strip()
                id = md5(f'{source}{pair}'.encode()).hexdigest()
                logger.info(f'{id}  {source} {pair} {price} {volume}')
                sql = f'({repr(id)},{repr(name)},{repr(source)},{repr(pair)},{repr(price)},{repr(volume)},{int(time.time())})'
                sqls.append(sql)
            except:
                logger.warning(f'{name} 该币无交易所信息')
                # 加入黑名单
                self.redis_cli.sadd(self.markets_blacklist, name)
                return
        if sqls:
            sql_all = sql_base.format(','.join(sqls))
            self.rds.insert(sql_all)
            self.redis_cli.sadd(self.markets_jobs_done,name)
        else:
            logger.warning(f'{name} 该币无交易所信息')
            # 加入黑名单
            self.redis_cli.sadd(self.markets_blacklist,name)

    def history_prices(self, name, content):
        """
        解析历史价格数据插入数据库
        """
        # 查询历史价格是否采集过，如果采集过了，那么就过滤
        logger.info(name)
        status = self.redis_cli.sismember(self.history_prices_done,name)
        if status:
            return
        pattern = """dataPoints: \[(.+?)\]"""
        res = re.findall(pattern, content, re.S)[1]
        content = res.strip().split('\n')
        sql_base = "replace into brc20_token_price (token_name,price,price_date) values {};"
        sql_list = []
        for i in content:
            newi = i.strip()
            if newi:
                date_time = re.findall("new Date\('(.+?)'\)", newi)[0]
                price = re.findall("y: (.+?) \}", newi)[0]
                # print(date_time, price)
                date_time_obj = datetime.datetime.strptime(date_time, '%Y-%m-%d %H:%M')
                timestamp = datetime.datetime.timestamp(date_time_obj)
                price_date = int(timestamp)
                sql_one = f'({repr(name)},{repr(price)},{price_date})'
                sql_list.append(sql_one)
        if sql_list:
            sqls = sql_base.format(','.join(sql_list))
            status = self.rds.insert(sqls)
            if status:
                self.redis_cli.sadd(self.history_prices_done,name)

    def run(self):
        num = 0
        # 起始时间
        start_time = int(time.time())
        while True:
            name = self.redis_cli.spop(self.markets_jobs)
            if name:
                # 每24小时重置一次任务完成清单（剔除去重再次从新开始任务，相当于24小时刷新一次）
                if (int(time.time()) - start_time) > 24*60*60:
                    self.redis_cli.delete(self.markets_jobs_done)
                    # 重置起始时间
                    start_time = int(time.time())
                # 无交易所信息黑名单
                status_black = self.redis_cli.sismember(self.markets_blacklist,name)
                if status_black:
                    continue
                # 24小时内是否采集过
                status_done = self.redis_cli.sismember(self.markets_jobs_done,name)
                if status_done:
                    continue
                num += 1
                # self.req(name)
                logger.info(f'{num} job {name} done')
                t = Thread(target=self.req, args=(name,))
                t.start()
                # 控制线程创建的速度
                time.sleep(0.1)
            else:
                num = 0

if __name__ == '__main__':
    # 得考虑如何24小时调度一次的问题，间歇性消费，弄个任务完成清单，该清单每24小时清空一次，24小时内作为任务去重标准
    Spider().run()


