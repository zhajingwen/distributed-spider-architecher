import logging
from multiprocessing import Process
from .gen_data.spider import GasSpider
from .server import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Program Entrence')

def task1():
    """
    每日GAS费告警推送并落库
    """
    GasSpider().run()

def task2():
    """
    bot server
    """
    app.run(host='0.0.0.0', port=93)

def run(spider_name):
    # ps = []

    p1 = Process(target=task1)
    p1.start()
    # ps.append(p1)
    #
    # p2 = Process(target=task2)
    # p2.start()
    # ps.append(p2)
    #
    # for p in ps:
    #     p.join()
    task2()