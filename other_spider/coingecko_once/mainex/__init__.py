import datetime
from .before_tradeinfo import MatchCKAndInitial
from other_spider.coingecko_once.spider_tradeinfo_from_redis import Spider

def mainex_main(spider_name):
    # 通过playwright拿到mainex全部上币数据 (常驻进程)
    if 'allcoins' in spider_name:
        # 依赖playwright
        from .names_symbols import NameSymbol
        NameSymbol().run()
    else:
        # 完成coingecko匹配和首发上币打标的工作
        if 'tradeinfo' not in spider_name:
            # 10.1-2024年1月1号0点
            start_time = 1696089600
            end_time = 1704038400
            MatchCKAndInitial('mainex').run(start_time, end_time)
        else:
            # 历史数据
            # 根据各个交易所上币清单 请求coingeck接口拿到历史交易数据
            today_now = datetime.datetime.now()
            today_now = today_now - datetime.timedelta(days=100)
            # 需要采集的季度，时间范围
            start = today_now.replace(month=10, day=1)
            end = today_now.replace(month=12, day=31)

            Spider('mainex').run(start, end)