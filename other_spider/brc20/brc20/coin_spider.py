import requests
import time
import json
import logging
from lxml import etree
from functools import wraps
from traceback import format_exc
from urllib.parse import urljoin
from threading import Thread
from utils.proxy_requests import proxies
from utils.rds import DataUtils
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Brc20 CoinList brc-20.io')
# PROXY_URL = '<PROXY_URL>'
# 格式化成 requests需要的格式类型
# proxies = {
#     'http': PROXY_URL,
#     'https': PROXY_URL
# }


class Spider:
    def __init__(self):
        # self.statistic_url = 'https://brc-20.io/'
        # self.statistic_url_2 = 'https://brc-20.io/volume_iframe'
        self.base_url = 'https://brc-20.io/index_page?page={}'
        self.headers = {
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.list_one_done = 'crawl-brc20:list1:done'
        self.price_update_timelimit_base = 'crawl-brc20:price:update_timelimit:{}'
        self.price_update_timelimitjob = 'crawl-brc20:price:update_timelimtjob'

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

    def price_to_history(self, price, name):
        """
        将最新价格刷入历史价格库的任务推送到redis
        """
        # 将当前价刷入历史数据表
        if price != 'null':
            # 每个币5分钟刷一次
            key = self.price_update_timelimit_base.format(name)
            status = self.redis_cli.get(key)
            # 当前币5分钟内没有更新过；才落库
            if not status:
                # 将插入历史价格库的任务递交给其他进程
                data = {
                    'price': price,
                    'name': name,
                    'time_stamp': int(time.time())
                }
                self.redis_cli.sadd(self.price_update_timelimitjob, json.dumps(data))
                # 任务递交后做递交记录，控制5分钟内不在递交
                self.redis_cli.setex(key, 5 * 60, int(time.time()))

    @retry()
    def req(self,num):
        """
        获取代币总量和总市值
        """
        url = self.base_url.format(num)
        logger.info(f'request: {url}')
        res = requests.get(url,headers=self.headers,proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        tree = etree.HTML(res.text)
        pages_pattern = '//h3[contains(./text(),"Pages")]/a[last()]/text()'
        # 第一次进入，开启翻页模式
        pages = tree.xpath(pages_pattern)[0]
        if pages:
            pages = int(pages)
            # 识别首次进入
            if num == 1:
                # 正常287页
                logger.info(f'总页数：{pages}')
                for i in range(2,pages+1):
                    # 多线程翻页请求并解析入库
                    t = Thread(target=self.req,args=(i,))
                    t.start()
                    # 控制并发数
                    time.sleep(1)
        pattern_num = 0
        pattern_list = tree.xpath('//table[@id="main_table"]/tr')
        # print(pattern_list)
        start_time = int(time.time())
        # logger.info(res)
        insert_sql_list = []
        insert_sql_allbase = 'insert into brc20_tokens values{};'
        # 定义 SQL 查询和参数
        # update_query = "UPDATE users SET email = %s WHERE id = %s"
        update_query = 'UPDATE brc20_tokens SET price=%s,market_value=%s,' \
                     'quote_change=%s,trans_amount=%s,mint_progress=%s,' \
                     'update_time=now(),limit_per_mint=%s WHERE name=%s'

        update_data = []
        names = []
        for pattern in pattern_list:
            pattern_num += 1
            # if pattern_num == 1:
            #     continue
            id = pattern.xpath('./td[1]/text()')[0].strip()
            name = pattern.xpath('./td[2]/a/text()')[0].strip()
            img = pattern.xpath('./td[2]/img/@src')
            if not img:
                img = 'null'
            else:
                img = img[0]
                img = urljoin(url, img).strip()
                img = repr(img)
            price = pattern.xpath('./td[3]/text()')
            if not price:
                price = 'null'
            else:
                price = price[0].strip().replace('$','')
                price = round(float(price),10)
            # 刷入历史价格表
            self.price_to_history(price,name)

            price_change_24 = pattern.xpath('./td[4]/text()')
            if not price_change_24:
                price_change_24 = 'null'
            else:
                price_change_24 = price_change_24[0].strip().replace('%','').replace(',','')
                price_change_24 = round(float(price_change_24),2)
                creased_status = pattern.xpath('./td[4]/i/@class')[0].strip()
                if 'down' in creased_status:
                    price_change_24 = price_change_24 * -1
            market_cap = pattern.xpath('./td[5]/text()')
            if not market_cap:
                market_cap = 'null'
            else:
                market_cap = market_cap[0].strip().replace('$','').replace(',','')
                market_cap = int(market_cap)
            volume_24 = pattern.xpath('./td[6]/text()')
            if not volume_24:
                volume_24 = 'null'
            else:
                volume_24 = volume_24[0].strip().replace('$','').replace(',','')
                volume_24 = int(volume_24)
            supply = pattern.xpath('./td[7]/text()')
            if not supply:
                supply = 'null'
            else:
                supply = supply[0].strip().replace(',','')
                supply = int(supply)
            minted = pattern.xpath('./td[8]/text()')
            if not minted:
                minted = 'null'
            else:
                minted = minted[0].strip().replace('%','')
                minted = round(float(minted),2)
            limit_per_mint = pattern.xpath('./td[9]/text()')
            if not limit_per_mint:
                limit_per_mint = 'null'
            else:
                limit_per_mint = limit_per_mint[0].strip().replace(',','')
                limit_per_mint = int(limit_per_mint)
            # logger.info(f'{id} {img} {name} {price} {price_change_24} {market_cap} {volume_24} {supply} {minted} {limit_per_mint}')
            # select_sql = f'select * from brc20_tokens where name={repr(name)}'
            # res = self.rds.select(select_sql)
            # mysql查询改reids查询，提升速度，否则太慢
            status = self.redis_cli.sismember(self.list_one_done,name)
            # 如果有记录就update
            if status:
                # update_sql = f'UPDATE brc20_tokens SET price={price},market_value={market_cap},' \
                #              f'quote_change={price_change_24},trans_amount={volume_24},' \
                #              f'mint_progress={minted},update_time=date() WHERE name={repr(name)}'
                update_one_data = (price,market_cap,price_change_24,volume_24,minted,limit_per_mint,name)
                update_one_data = tuple(None if x == 'null' else x for x in update_one_data)
                update_data.append(update_one_data)
            else:
                # if market_cap != 'null':
                #     market_cap = repr(market_cap)
                if name in names:
                    continue
                insert_sql = f'({repr(id)},{repr(name)},{img},{price},{market_cap},' \
                             f'{price_change_24},{volume_24},{minted},null,now(),now(),{supply},{limit_per_mint},null)'
                insert_sql_list.append(insert_sql)
                names.append(name)
        if insert_sql_list:
            insert_sqls = insert_sql_allbase.format(','.join(insert_sql_list))
            while True:
                status = self.rds.insert(insert_sqls)
                if status:
                    logger.info(f'插入成功 {insert_sqls.split("into")[0]} into')
                    break
                else:
                    logger.info('切换成 replace into 插入模式')
                    time.sleep(2)
                    insert_sqls = insert_sqls.replace('insert into','replace into')

            # 插入成功
            if status:
                # 首次插入后记录到redis
                with self.redis_cli.pipeline(transaction=False)as pipe:
                    for name in names:
                        pipe.sadd(self.list_one_done,name)
                    pipe.execute()
        if update_data:
            self.rds.update_many(update_query,update_data)
        logger.info(f'page: {num} 耗时：{int(time.time())-start_time} s')

    def run(self):
        while True:
            self.req(1)
            # 休息两分钟
            time.sleep(2*60)



if __name__ == '__main__':
    Spider().run()
