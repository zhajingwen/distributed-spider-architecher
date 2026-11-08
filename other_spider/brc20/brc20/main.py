import sys
from coin_spider import Spider as SpiderList1
from other_spider.brc20.coin_spider_2 import Spider as SpiderList2
from coin_markets_and_historyprices import Spider as CoinMarkets
from price_to_historydatabase import Spider as PricetoHistorySpider
from all_markets_spider import Spider as OverViewSpider
from gasfee import Spider as GasfeeSpider
"""
# 采集unsiat的依赖
python3 fuck_cf.py gen
python3 fuck_cf.py ipmonitor
# brc-20.io 爬虫
python3 main.py SpiderList1
unisat爬虫
python3 main.py SpiderList2
python3 main.py CoinMarkets
python3 main.py OverViewSpider
python3 main.py GasfeeSpider
python3 main.py PricetoHistorySpider
"""


# 获取脚本名称
print("脚本名称：", sys.argv[0])
# 获取命令行参数
spider_name = sys.argv[1]
print("命令行参数：", spider_name)
# 生产cf cookie的程序
if spider_name == 'SpiderList1':
    SpiderList1().run()
elif spider_name == 'SpiderList2':
    SpiderList2().run()
# 交易所信息和历史价格信息 （交易所24小时刷一次，历史价格只更新一次）
elif spider_name == 'CoinMarkets':
    CoinMarkets().run()
# 将最新价刷入历史价格表（依赖 python3 main.py SpiderList1 的任务传递）
elif spider_name == 'PricetoHistorySpider':
    PricetoHistorySpider().run()
elif spider_name == 'OverViewSpider':
    OverViewSpider().run()
elif spider_name == 'GasfeeSpider':
    GasfeeSpider().run()

