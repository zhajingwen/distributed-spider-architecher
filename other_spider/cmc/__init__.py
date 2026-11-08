# import time
from .monitor import Spider
from .tg_bot2 import Spider as MX
from .backtest import GenCurrency
from .monitor2 import Spider as Spider2
from .high_exchange_rate import Spider as StrongSpider
from .monitor3 import Spider as Spider3


def run(spider_name):
    """
    python3 manage.py -e local -s cmc.test
    nohup python manage.py -e prod -s cmc.m3 > cmcm3.log &
    nohup python manage.py -e prod -s cmc.m2 > cmcm2.log &
    """
    if spider_name == 'm':
        Spider().run()
    # elif spider_name == 'tg':
    #     MX().run()
    elif spider_name == 'm2':
        Spider2().run()
    # elif spider_name == 'backtest':
    #     GenCurrency().time_interval()
    elif spider_name == 'strong':
        StrongSpider().run()
    elif spider_name == 'm3':
        Spider3().run()
    else:
        print('指令错误！')
    #     Spider().run()

