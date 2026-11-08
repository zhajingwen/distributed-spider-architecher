# import datetime
# from .mexc import main
# from .Q3 import Spider
# from .mainex.before_tradeinfo import MatchCKAndInitial
from other_spider.coingecko_once.mexc import mexc_main
from other_spider.coingecko_once.mainex import mainex_main
from other_spider.coingecko_once.gate import gate_main

def run(spider_name):
    """
    执行流程(彼此存在依赖关系，依次执行)：
    python manage.py -e prod -s coingecko_once.mexc
    python manage.py -e local -s coingecko_once.mexc
    python manage.py -e prod -s coingecko_once.tradeinfo
    """
    # 抹茶通过上币公告，拿到上币清单 导出数据给分析师确认
    if "mexc" in spider_name:
        mexc_main(spider_name)
    elif 'mainex' in spider_name:
        # 每次执行前需要设置redis key          self.last_coin = 'mainex:lastcoin'  为上一季度最后一个币的 symbol
        mainex_main(spider_name)
    elif 'gate' in spider_name:
        gate_main(spider_name)
    else:
        print('指令错误')