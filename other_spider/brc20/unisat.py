import time
import json
import datetime
import logging
import os
from functools import wraps
from traceback import format_exc
from math import ceil
from threading import Thread
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from .retry import retry_net
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 Unisat')
env = os.environ.get('env')


class Unisat:
    def __init__(self):
        self.base_url = 'https://api.unisat.io/query-v4/brc20/status?ticker_hex=&start={}&limit=20&complete=&sort=transactions'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.unisat_done = 'crawl-brc20:unisat_playwright:done'
        self.cookies_store = 'crawl-brc20:unisat_playwright:cookies'
        self.lark_url = os.getenv('LARK_WEBHOOK_BRC20', '')
        self.black_list = 'crawl-brc20:unisat_playwright:alert:blacklist'

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
        # 第一次进入，开启翻页模式
        pages = ceil(data['total'] / 500)
        if pages:
            # 识别首次进入
            if num == 0:
                logger.info(f'总页数：{pages}')
                # 只采集前60页
                if pages > 60:
                    pages = 60
                for i in range(1, pages):
                    # 多线程翻页请求并解析入库
                    t = Thread(target=self.req, args=(i * 500,))
                    t.start()
                    # 由于上了cf 限制频率，免得打死了
                    time.sleep(10)
        start_time = int(time.time())
        update_query = 'UPDATE brc20_unisat SET holders_amount=%s,online_time=%s,' \
                       'update_time=now(),transactions=%s,transaction_24h=%s,' \
                       'progress_24h=%s,mint_progress=%s WHERE name=%s'
        update_data = []

        repalce_into_sqls = 'replace into brc20_unisat values {};'
        insert_data = []
        names = []
        detail = data['detail']
        for item in detail:
            name = item['ticker']
            name = name.lower()
            holdersCount = item['holdersCount']
            deployBlocktime = item['deployBlocktime']
            progress = (item['completeHeight'] / item['deployHeight']) * 100
            if progress > 100:
                progress = 100
            if progress < 1:
                progress = 0
            transactions = item['historyCount']
            dt_object = datetime.datetime.fromtimestamp(deployBlocktime)
            deploy_date = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            # 是否插入过
            have_insert_status = self.redis_cli.sismember(self.unisat_done,name)
            if not have_insert_status:
                insert_sql = f'({repr(name)},{progress},{holdersCount},{repr(deploy_date)},{transactions},null,null,now(),now())'
                insert_data.append(insert_sql)
                names.append(name)
                # 跳过update处理
                continue
            # 查询历史数据计算24小时新增量
            res_24h = self.gen_24h_data(name, progress, transactions)
            if res_24h:
                progress_24h, transactions_24h = res_24h
                update_one_data = (holdersCount, deploy_date, transactions, transactions_24h, progress_24h, progress, name)
                update_data.append(update_one_data)
                names.append(name)
                # 推送到lark
                self.alert(item)
        if update_data:
            # 测试任务不设定早上刷新
            if env == 'test':
                self.update_mysql_test(update_query, update_data, names)
            # 线上生产
            else:
                # 每日7点-7点10分分才更新一次
                self.update_mysql(update_query, update_data, names)

        # 插入随时进行不需要在早上固定时间段
        if insert_data:
            sqls = ','.join(insert_data)
            new_insert_sqls = repalce_into_sqls.format(sqls)
            status = self.rds.insert(new_insert_sqls)
            if status:
                # 首次插入后记录到redis
                with self.redis_cli.pipeline(transaction=False)as pipe:
                    for name in names:
                        pipe.sadd(self.unisat_done,name)
                    pipe.execute()
        logger.info(f'page: {num} 耗时：{int(time.time()) - start_time} s')

    def update_mysql(self, update_query, update_data, names):
        """
        由于要算24H mint进度数据，故数据库24小时刷新一次
        """
        today_now = datetime.datetime.now()
        today_at_07 = today_now.replace(hour=7, minute=0, second=0)
        today_at_07_10 = today_now.replace(hour=7, minute=10, second=0)
        # 每日07点刷新一次unisat数据
        if today_at_07 < today_now < today_at_07_10:
            status = self.rds.update_many(update_query, update_data)
            # 插入成功
            if status:
                logger.info(f'update successfully {names}')
            else:
                logger.error(f'update failed {names}')

    def update_mysql_test(self, update_query, update_data, names):
        """
        由于要算24H mint进度数据，故数据库24小时刷新一次
        """
        # 入库返回值
        status = self.rds.update_many(update_query, update_data)
        # 插入成功
        if status:
            logger.info(f'update successfully {names}')
        else:
            logger.error(f'update failed {names}')

    def gen_24h_data(self, name, progress, transactions):
        """
        生成24小时转账次数
        24小时mint进度
        """
        # if '"' in name:
        #     name = name.replace()
        sql = f'select mint_progress,transactions from brc20_unisat where name={repr(name)};'
        result = self.rds.select(sql)
        if result:
            result = result[0]
            old_mint_progress = result['mint_progress']
            if old_mint_progress:
                # TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'
                # progress_24h = progress - old_mint_progress
                progress_24h = progress - float(old_mint_progress)
            else:
                progress_24h = progress
            old_transactions = result['transactions']
            if old_transactions:
                transactions_24h = transactions - float(old_transactions)
            else:
                transactions_24h = transactions
            return progress_24h, transactions_24h
        else:
            return None


    def rule_judge1(self, data):
        """
        条件1
        通过 返回True
        """
        status = False
        # 部署时间不得超过一周
        deploy_blocktime = data['deployBlocktime']
        if int(time.time()) - deploy_blocktime < 7 * 24 * 60 * 60:
            # mint进度约束
            progress = (data['completeHeight'] / data['deployHeight']) * 100
            if progress >= 20 and progress < 100:
                if progress > 100:
                    progress = 100
                holders = data['holdersCount']
                # holders约束
                if holders >= 300:
                    transactions = data['historyCount']
                    # transactioins约束
                    if transactions >= 300:
                        status = True
        return status

    def rule_judge2(self, data):
        """
        条件2
        通过 返回True
        """
        status = False
        # 部署时间不得超过一周
        deploy_blocktime = data['deployBlocktime']
        if int(time.time()) - deploy_blocktime < 7 * 24 * 60 * 60:
            # mint进度约束
            progress = (data['completeHeight'] / data['deployHeight']) * 100
            if progress > 100:
                progress = 100
            if progress == 100:
                holders = data['holdersCount']
                # holders约束
                if holders >= 500:
                    transactions = data['historyCount']
                    # transactioins约束
                    if transactions >= 1000:
                        status = True
        return status

    def alert(self, data):
        """
        lark 推送
        """
        # # 部署时间不得超过一周
        deploy_blocktime = data['deployBlocktime']
        progress = (data['completeHeight'] / data['deployHeight']) * 100
        if progress > 100:
            progress = 100
        holders = data['holdersCount']
        transactions = data['historyCount']
        ticker = data['ticker']
        ticker = ticker.lower()
        dt_object = datetime.datetime.fromtimestamp(deploy_blocktime)
        # 将datetime对象转换成字符串
        date_string = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        # 只要有一个条件满足就报警
        if self.rule_judge1(data) or self.rule_judge2(data):
            content = f"""
            币名：{ticker}
            部署具体时间：{date_string}
            mint总进度：{progress}%
            Holder：{holders}
            Transation：{transactions}
            """
            if self.redis_cli.sismember(self.black_list,ticker):
                logger.info(f'告警过了：{ticker}')
                return
            sender(content, self.lark_url, 'brc20')
            # 报警后加入去重队列
            self.redis_cli.sadd(self.black_list,ticker)

                        # res_24h = self.gen_24h_data(ticker, progress, transactions)
                        # if res_24h:
                        #     progress_24h, transactions_24h = res_24h
                        #     if progress_24h >= 10:
                        #         content = f"""
                        #         币名：{ticker}
                        #         部署具体时间：{date_string}
                        #         mint总进度：{progress}%
                        #         24H增加进度值：{progress_24h}%
                        #         当日转账次数：{transactions_24h}
                        #         Holder：{holders}
                        #         Transation：{transactions}
                        #         """
                        #         sender(content, self.lark_url, 'brc20')
                        # if res_24h:
                        #     progress_24h, transactions_24h = res_24h
                        #     if progress_24h >= 10:

    def run(self):
        # 测试
        if env != 'prod':
            self.req(0)
        else:
            while True:
                self.req(0)
                # 5分钟刷新一次
                # 想以1分钟为单位进行测试；
                time.sleep(5 * 60)


if __name__ == '__main__':
    Unisat().run()
