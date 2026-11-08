import time
import os
import logging
import requests
import re
import queue
import json
# from multiprocessing import Process
from utils.redisdb import redis_cli
from concurrent.futures import ThreadPoolExecutor

env = os.environ.get('env')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Cookies Gen')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class Gen:
    def __init__(self, project_name, url):
        """
        project_name: 项目名
        url：需要绕过cf的网站
        """
        self.cookies_store = f'{project_name}:cookies'
        self.ip_store_key = f'{project_name}:ips:store'
        # 线程数
        self.excutor = MyThreadPoolExecutor(max_workers=1)
        # 每个ip间隔60s
        self.delay_everyip = 60
        # 每批次间隔时间 30分钟（所有ip遍历生成一遍cooKies为一个批次）
        self.delay_everybatch = 30*60
        self.url = url

    def parse_proxy(self, proxy):
        """
        格式化
        """
        if "@" in proxy:
            proxy_regex = re.match("(.+)://(.+):(.+)@(.+)", proxy)
            server = f"{proxy_regex.group(1)}://{proxy_regex.group(4)}"

            proxy_params = {
                "server": server,
                "username": proxy_regex.group(2),
                "password": proxy_regex.group(3),
            }
        else:
            proxy_params = {"server": proxy}

        return proxy_params

    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            # logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

    def rpc_gen(self, ips, redis_c, ip_store_key, id):
        """
        get cf cookies from web server
        """
        ip = ips[id]
        proxy_url = ip
        browser_proxy = self.parse_proxy(proxy_url)
        num = 0
        # 连接失败重试
        while True:
            # 最多重试一次，防止有IP下线，占用线程池，如果这样的IP有10个（进程池是10），那么就会导致进程假死
            num += 1
            if num > 2:
                return
            try:
                logger.info(f'请求rpc处理：{browser_proxy}')
                resp = requests.post(
                    "https://example.com/challenge",
                    json={
                         "proxy": browser_proxy,
                         "timeout": 30*60,
                         "url": self.url
                     },
                    timeout=20*60
                )
                break
            except:
                logger.warning(f'连接失败{browser_proxy}')
                time.sleep(3)
        res = resp.json()
        if not res.get("success"):
            redis_c.hdel(ip_store_key, id)
            logger.warning(f'代理失败{res}，删除{id}：{ip}')
            return
        else:
            cf = ''
            if res['cookies']:
                logger.info(res['cookies'])
                cf = res['cookies'].get('cf_clearance', '')
            cookie_seed = {
                "id": id,
                "proxy": ip,
                "ua": res['user_agent'],
                "cf": res['cookies'],
                "timestamp": int(time.time())
            }
            # if not cf:
            #     cookie_seed.pop('cf')
            redis_c.sadd(self.cookies_store, json.dumps(cookie_seed))
            logger.info(f'新的代理已经入库：{id}')

    def check_ips(self):
        """
        遍历redis中所有的IP
        生成IP对应的cookie
        """
        redis_c = redis_cli()
        ips = redis_c.hgetall(self.ip_store_key)
        for id in ips:
            if not id:
                logger.info('当前所有IP遍历完了')
                return
            # 线程池调用
            self.excutor.submit(self.rpc_gen, ips, redis_c, self.ip_store_key, id).add_done_callback(self.executor_callback)
            time.sleep(self.delay_everyip)

    def gen_loop(self):
        num = 0
        while True:
            logger.info('hgetall获取所有ip，请耐心等待')
            # 启动会卡75s左右，hget耗时
            self.check_ips()
            num += 1
            logger.info(f'当前ip列表已经刷完{num}遍了')
            # 半小时刷一次，否则容易把IP跑废，测试发现连续跑，IP容易废掉
            time.sleep(self.delay_everybatch)

