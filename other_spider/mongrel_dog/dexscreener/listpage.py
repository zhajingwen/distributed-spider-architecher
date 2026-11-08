import time
import websocket
import ssl
import os
import base64
import json
import logging
from math import ceil
from functools import wraps
from traceback import format_exc
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Dexscreener')

# 看到网上有不少推荐使用该库的，测试下来该库无法实现，也是耽误了我一天的时间，各种调试，一开始只是以为是我没有过风控的问题，其实并不是，问题在库上；该项目已经4年没有更新了，废掉了，不建议使用
# from aiowebsocket.converses import AioWebSocket
#https://github.com/asyncins/aiowebsocket

class ListPage:
    def __init__(self):
        self.base_url = 'wss://io.dexscreener.com/dex/screener/pairs/h24/{}?rankBy[key]=txns&rankBy[order]=desc&filters[liquidity][min]=100000&filters[marketCap][min]=200000&filters[txns][h24][min]=100'
        self.base_url = 'wss://io.dexscreener.com/dex/screener/pairs/h24/1?rankBy[key]=txns&rankBy[order]=desc&filters[liquidity][min]=100000&filters[marketCap][min]=200000&filters[txns][h24][min]=100'
        self.redis_cli = redis_cli()
        self.page_list_key = 'mongrel:dexscreener:pagelist'

    def generate_websocket_key(self):
        # 生成一个16字节的随机值
        buffer = os.urandom(16)
        # 将随机值进行Base64编码
        key = base64.b64encode(buffer).decode('utf-8')
        return key

    def open_connection(self, num):
        """
        建立连接
        """
        header = {
                # 用户唯一性校验+风控识别校验，可以理解为mac地址的作用，该值有一定的规范，是随机生成的，但是得符合一定的标准，在标准之外的随机数是不被认可的，无法建立连接
                # "Sec-WebSocket-Key": self.generate_websocket_key(),
                # 和http请求的用途一样，用于校验客户端角色；主要风控
            "Origin": "https://dexscreener.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
            }

        ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        # remote = 'wss://io.dexscreener.com/dex/screener/pairs/h24/4??rankBy[key]=txns&rankBy[order]=desc&filters[liquidity][min]=100000&filters[marketCap][min]=200000&filters[txns][h24][min]=100'
        url = self.base_url.format(num)
        logger.info(f'request {num}: {url}')
        # 必须得携带头部信息，Python代码实现的wss通信自动生成的Sec-WebSocket-Key 很多服务器会不支持
        ws.connect(url, header=header, suppress_origin=True)
        return ws

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
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'ConnectionRefusedError' in error:
                            logger.warning(f'{func.__name__} ConnectionRefusedErr')
                        elif 'json.decoder.JSONDecodeError' in error:
                            logger.warning(f'{func.__name__} JSONDecodeErr')
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

    @retry(5)
    def get_data(self, num):
        """
        发起请求获取数据
        """
        retry_num = 0
        while True:
            retry_num += 1
            if retry_num > 3:
                logger.error('重试超过次数！')
                return
            try:
                ws = self.open_connection(num)
                # message = input("Enter message: ")
                # 测了下好像不会过期(约20个小时)   该行代码有可能报错
                # ws.send('pong')
                ws.pong()
                break
            except:
                logger.warning('wss通信失败，重试...')
                time.sleep(1)
        response = ws.recv()
        logger.info(f'response: {num}')
        data = json.loads(response)
        # 解析入goplus任务队列 + 翻页
        self.parse(data, num)

    def parse(self, data, num):
        """
        1、解析数据推入 goplus任务队列
        2、翻页
        """
        pairsCount = data.get('pairsCount')
        # 翻页操作
        if pairsCount:
            # 计算页数
            pages = ceil(pairsCount / 100)
            # 有下一页才翻
            if pages > 1:
                # 首次调用才进行迭代翻页
                if num == 1:
                    logger.info(f'总页数：{pages} {pairsCount}')
                    for n in range(2,pages+1):
                        logger.info(f'turn page {n}')
                        # 传入页码
                        self.get_data(n)
                        # 3s 间隔防止风控
                        time.sleep(3)
        pairs = data['pairs']
        for p in pairs:
            self.redis_cli.sadd(self.page_list_key,json.dumps(p))
            logger.info(f'入库：{p}')

    def run(self):
        """
        启动入口
        单线程
        """
        while True:
            # 1 表示第一页，初始化值
            self.get_data(1)
            logger.info(f'当前批次跑完，等待下次执行...')
            # 一个小时跑一次
            time.sleep(60*60)

