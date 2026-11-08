import datetime
from .refresh_new_coin import RefreshNewCoin
from .once_added import Once
from .match_ck import GateMatchCK
from other_spider.coingecko_once.spider_tradeinfo_from_redis import Spider

def gate_main(spider_name):
    market = 'gate'
    # 10.1-2024年1月1号0点
    start_time = 1696089600
    end_time = 1704038400
    # 刷新统计区间内的上币清单  （常驻进程）
    if 'refresh' in spider_name:
        RefreshNewCoin(market).refresh_24H(start_time, end_time)
    # 刷新统计区间内的上币清单  （常驻进程） playwright版本
    if 'playwright' in spider_name:
        from .refresh_new_coin_playwright import NewCoinPlaywright
        NewCoinPlaywright(market, start_time, end_time).run()
    # 首次执行的补数据，只跑一次
    elif 'once' in spider_name:
        Once(market).run(start_time, end_time)
    # 与coingecko做匹配
    elif 'match' in spider_name:
        GateMatchCK(market).match()
    # 历史数据(在match后执行)
    else:
        # 根据各个交易所上币清单 请求coingeck接口拿到历史交易数据
        today_now = datetime.datetime.now()
        today_now = today_now - datetime.timedelta(days=100)
        # 需要采集的季度，时间范围
        start = today_now.replace(month=10, day=1)
        end = today_now.replace(month=12, day=31)

        Spider('gate').run(start, end)