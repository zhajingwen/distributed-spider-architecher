import time
from .etherscan import EtherScan
from .nansen import Nansen
from .tokenterminal import TokenTerminal

def run(spider_name):
    """
    python3 manage.py -e local -s crypto_scan.eth
    python3 manage.py -e local -s crypto_scan.eth
    python3 manage.py -e local -s crypto_scan.eth

    nohup python manage.py -e prod -s crypto_scan.eth > crypto_scan_eth.log &
    nohup python manage.py -e prod -s crypto_scan.nansen > crypto_scan_nansen.log &
    nohup python manage.py -e prod -s crypto_scan.tt > crypto_scan_tt.log &
    """
    # 15分钟跑一次
    # while True:
    if spider_name == 'eth':
        EtherScan().run()
    elif spider_name == 'nansen':
        Nansen().run()
    else:
        TokenTerminal().run()


