import time
import logging
import json
import queue
from other_spider.dexfilter.spiders.retry import retry,retry_net
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('USER_A SPIDER')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class PoolInfo:
    def __init__(self):
        self.headers = {
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'sec-ch-ua': '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
            'accept': 'application/json, text/plain, */*',
            'dnt': '1',
            'sec-ch-ua-mobile': '?0',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko)',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://dexfilter.com/',
            'accept-encoding': 'gzip',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7'
        }
        # self.filter = Filter()
        self.redis_cli = redis_cli()
        self.redis_poolinfo_jobkey = 'dexfilter:user_a:poolinfo'
        self.cookies_store = 'dexfilter:cookies'
        self.excutor = MyThreadPoolExecutor(max_workers=20)
        self.rds = DataUtils('spider')
        self.base_url = 'https://dexfilter.com/v1/{}/getRightPondInfo?tag={}'

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hood
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
            if (int(time.time()) - timestamp) > 30*60:
                logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry(3)
    def req(self, url):
        """
        common req function
        """
        cookie_dict = self.get_cookie()
        logger.info(f'request: {url}')
        # {"id": "718fd558da3df70d254df15dc52944f8", "proxy": "<PROXY_URL>", "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36", "cf": "<CF_CLEARANCE>", "timestamp": 1671091997}
        # 以下三项均来自rpc
        self.headers['user-agent'] = cookie_dict['ua']
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        res = retry_net(cookie_dict, url, self.headers, proxies)
        if not res:
            return
        logger.info(f'response code: {res.status_code} {url}')
        # 当响应码异常的时抛出异常让重试装饰器重试
        if res.status_code in [403,500,502,503,504]:
            logger.info(f'{cookie_dict} {res.status_code} err 准备重试...')
            raise Exception(f'{res.status_code}')
        if res.status_code != 200:
            logger.error(f'响应码异常 {res.status_code} {url}')
            return
        res_data = res.json()
        code = res_data['code']
        # 响应体异常
        if code != 200:
            raise Exception(f'{code}')
        self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

    def getinfo(self, data):
        """
        get different ingterval data about tradeinfo
        """
        chain = data['chain']
        token = data['token']
        url = self.base_url.format(chain,token)
        res = self.req(url)
        if not res:
            return
        req_data = res.json()
        if not req_data:
            logger.warning(f'数据为空 {url} {req_data}')
            return
        if not req_data.get('data'):
            logger.warning(f'数据为空 {url} {req_data}')
            return
        if not req_data['data'].get('list'):
            logger.warning(f'数据为空 {url} {req_data}')
            return
        if not isinstance(req_data['data'],dict):
            logger.warning(f'类型错误：{req_data} {url}')
            return
        self.parse(data, res)

    def parse(self, data, response):
        """
        parse the tradeinfo response
        """
        res_data = response.json()
        address = data['token']
        totalname = data['tn']
        symbol = data['sy']
        spider_date_h = time.strftime("%Y-%m-%d %H", time.localtime(int(time.time())))
        dexfilter_id = data['id']
        for item in res_data['data']['list']:
            pair = item['pair']
            swap = item['swap']
            ub = item['total']['ub']
            vn = item['total']['vn']
            address_addresss = item['address']
            sql = f"replace into dexfilter_user_a_c values({repr(address)},{repr(totalname)},{repr(symbol)}," \
                  f"{repr(pair)},{repr(swap)},{ub},{vn},{repr(spider_date_h)},{repr(dexfilter_id)}," \
                  f"{repr(address_addresss)});"
            self.rds.insert(sql)

    def consumer(self):
        """
        执行当前批次的列表页产生的任务，采集详情
        执行完跳出循环
        """
        num = 0
        while True:
            data = self.redis_cli.spop(self.redis_poolinfo_jobkey)
            if data:
                data = json.loads(data)
                self.excutor.submit(self.getinfo, data).add_done_callback(self.executor_callback)
            else:
                # 每10分钟打印一次日志
                num += 1
                if num % 200 == 0:
                    logger.warning('当前任务执行完毕,等待新任务进来')
                time.sleep(3)

    def create(self):
        self.rds.create_table()