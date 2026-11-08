import asyncio
import logging
import time
from multiprocessing import Process
from other_spider.birdeye.gendata.update_gen_keys import GenKeys
from other_spider.birdeye.gendata.find_gems import FindGems
from .server import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Program Entrence')

def task1():
    # 生成cloudflare所需要的ID
    asyncio.run(GenKeys().run())

def task2():
    """
    bot server
    """
    app.run(host='0.0.0.0', port=92)

def task3():
    """
    爬虫数据落库
    """
    while True:
        try:
            FindGems().schedule()
            break
        except:
            logger.info(f'爬虫数据入库异常，准备重试...')
            time.sleep(10*60)

def run(spider_name):
    ps = []

    p1 = Process(target=task1)
    p1.start()
    ps.append(p1)

    p2 = Process(target=task2)
    p2.start()
    ps.append(p2)

    p3 = Process(target=task3)
    p3.start()
    ps.append(p3)
    for p in ps:
        p.join()