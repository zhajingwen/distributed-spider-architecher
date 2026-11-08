import json
import logging
import queue
import requests
from concurrent.futures import ThreadPoolExecutor
from retry import retry
from fake_useragent import UserAgent
from utils.proxy_requests import proxies
from .send_message import Send

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('De.fi Spider')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)

class DefiBalance():
    def __init__(self):
        # 线程数
        self.excutor = MyThreadPoolExecutor(max_workers=20)
        self.ua = UserAgent()
        # self.db = DataUtils('spider')
        self.base_url = 'https://api.de.fi/v1/account/sse?addresses%5B%5D={}' \
                   '&chains%5B%5D=1&chains%5B%5D=2&chains%5B%5D=3&chains%5B%5D=4' \
                   '&chains%5B%5D=5&chains%5B%5D=6&chains%5B%5D=7&chains%5B%5D=8' \
                   '&chains%5B%5D=13&chains%5B%5D=14&chains%5B%5D=17&chains%5B%5D=20' \
                   '&chains%5B%5D=31&chains%5B%5D=47&chains%5B%5D=48&chains%5B%5D=49&events%5B%5D=balances'
        self.headers = {
            "Accept": "event-stream",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.send = Send()

    def executor_callback(self, worker):
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            # logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

    def parse_address(self, content, open_id):
        """
        将用户发给机器人的消息解析成地址列表
        将每个地址作为任务发给爬虫处理
        """
        addresses = content.strip().split('\n')
        for address in addresses:
            url = self.base_url.format(address)
            self.excutor.submit(self.req, url, address, open_id).add_done_callback(self.executor_callback)


    @retry(tries=3, delay=3)
    def req(self, url, address, open_id):
        logger.info(f'Req: {url}')
        # response = requests.get(url, headers=headers, proxies=self.proxies, verify=False)
        # response = requests.get(url, headers=headers)
        # response = requests.get(url, headers=headers, proxies=self.proxies)
        response = requests.get(url, headers=self.headers, proxies=proxies, stream=True)
        logger.info(f'Response: {response.status_code} {url}')
        if response.status_code != 200:
            raise Exception(f'响应码错误：{response.status_code} 准备重试...')
        self.parse(response, address, open_id)

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num/1000000000),2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num/1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    def parse(self, response, address, open_id):
        """
        解析出地址余额
        """
        balance = 0
        for line in response.iter_lines(decode_unicode=True):
            if line:
                if isinstance(line, str):
                    if 'data: ' in line:
                        data = line.split('data: ')[-1]
                        data = json.loads(data)
                        # 有可能是空字典
                        if data:
                            #
                            totalValue = data[address]['totalValue']
                            balance += totalValue
        balance = self.num_transform(balance)
        logger.info(f'{address}: {balance}U')
        alert_content = f'地址：{address}  余额：{balance} U'
        self.send.send(open_id, alert_content)