from .inno_list import Spider
from .coin_list import RefreshCoinlist
from .newcoin_alert import NewCoinAlert

def run(spider_name):

    if spider_name == 'coinlist':
        RefreshCoinlist().run()
    elif spider_name == 'newcoinalert':
        NewCoinAlert().consumer()
    else:
        Spider().run()
