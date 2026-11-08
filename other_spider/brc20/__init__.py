from .coin_spider import Spider as Spider1List
from .coin_spider_2 import Spider as Spider2List
from other_spider.brc20.ips.to_redis import IpStore
from other_spider.brc20.cookies import Gen
from .minted_progress import Spider as ProgressSpider
from other_spider.brc20.unisat_playwright.uplay import UPlaywright
from other_spider.brc20.unisat import Unisat



def run(spider_name):
    if spider_name == 'brc-20':
        Spider1List().run()
    # 生产cf cookie的程序
    elif spider_name == 'gencookies':
        # 首次启动延迟两分钟，由于hgetall比较耗时
        Gen().gen_loop()
    # 列表页
    elif spider_name == 'ipmonitor':
        IpStore().ipstore_monitor()
    # 从unisat补全mintprogress数据
    elif spider_name == 'progress':
        ProgressSpider().run()
    # 报警程序 当前正在使用的
    elif spider_name == 'unisat_playwright':
        UPlaywright().run()
    # 报警程序
    elif spider_name == 'unisat_api':
        Unisat().run()
    else:
        # 合并多字段
        Spider2List().run()
