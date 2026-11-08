import logging
from multiprocessing import Process
from .gen_data.spider import GasSpider
from .server import app
from .refresh_allcoins_marketshare import Job

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Program Entrence')

def task1():
    """
    每日早晨8点刷新mainex已上线所有币的Marketshare status to RDS
    """
    Job().schedule()

def task2():
    """
    bot server
    """
    app.run(host='0.0.0.0', port=94)

def run(spider_name):
    if spider_name == 'refresh':
        task1()
    elif spider_name == 'server':
        task2()
    else:
        logger.error(f'指令错误：{spider_name}')

    # p1 = Process(target=task1)
    # p1.start()
    # task2()
    # p1.join()
    # app.run(host='0.0.0.0', port=94)
    # task1()