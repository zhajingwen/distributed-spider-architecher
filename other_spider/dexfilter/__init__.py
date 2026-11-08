# from multiprocessing import Process
# from .spiders import first,two
# # from .cookies.gen_cookies import run as cookierun
from .ips.to_redis import IpStore
from .cookies import Gen
from .spiders import List,Detail
from .user_a import MatchRules,NoMatch,TradeInfo,PoolInfo



def run(spider_name):
    """
    nohup python manage.py -e prod -s dexfilter.list > dexfilterlist.log &
    nohup python manage.py -e prod -s dexfilter.detail > dexfilterdetail.log &
    nohup python manage.py -e prod -s dexfilter.gen > dexfiltergen.log &
    nohup python manage.py -e prod -s dexfilter.ips > dexfilterips.log &
    nohup python manage.py -e prod -s dexfilter.user_a1 > dexfilteruser_a1.log &
    nohup python manage.py -e prod -s dexfilter.user_a2 > dexfilteruser_a2.log &
    nohup python manage.py -e prod -s dexfilter.user_a3 > dexfilteruser_a3.log &
    """
    # 生产cf cookie的程序
    if spider_name == 'gen':
        # 首次启动延迟两分钟，由于hgetall比较耗时
        Gen().gen_loop()
    # 列表页
    elif spider_name == 'list':
        List().run()
    # 详情页
    elif spider_name == 'detail':
        Detail().consumer()
    elif spider_name == 'user_a1':
        NoMatch().run()
    elif spider_name == 'user_a2':
        TradeInfo().consumer()
    elif spider_name == 'user_a3':
        PoolInfo().consumer()
    else:
        IpStore().ipstore_monitor()