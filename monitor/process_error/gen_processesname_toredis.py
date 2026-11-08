from utils.redisdb import redis_cli
import time
import os
redis_c = redis_cli()

def run(spidername):
    content = """nohup python manage.py -e prod -s premint.webapi > premint.log &
    nohup python manage.py -e prod -s gem.detail > gemdetail.log &
    nohup python manage.py -e prod -s gem.list > gemlist.log &
    nohup python manage.py -e prod -s gem.list1h > gemlist1h.log &
    nohup python manage.py -e prod -s gem.list15m > gemlist15m.log &
    nohup python manage.py -e prod -s cmc.m > cmcm.log &
    nohup python manage.py -e prod -s cmc.tg > cmctg.log &
    nohup python manage.py -e prod -s cmc.m14 > cmcm14.log &
    nohup python manage.py -e prod -s twitterscan.run > twitterscan.log &
    nohup python manage.py -e prod -s googletrends.t > googletrends.log &
    nohup python manage.py -e prod -s dexfilter.list > dexfilterlist.log &
    nohup python manage.py -e prod -s dexfilter.detail > dexfilterdetail.log &
    nohup python manage.py -e prod -s dexfilter.gen > dexfiltergen.log &
    nohup python manage.py -e prod -s dexfilter.ips > dexfilterips.log &
    nohup python manage.py -e prod -s dexfilter.user_a1 > dexfilteruser_a1.log &
    nohup python manage.py -e prod -s dexfilter.user_a2 > dexfilteruser_a2.log &
    nohup python manage.py -e prod -s dexfilter.user_a3 > dexfilteruser_a3.log &
    nohup python manage.py -e prod -s cmc_history.spider > cmchistoryspider.log &
    nohup python manage.py -e prod -s nswap.list > nswaplist.log &
    nohup python manage.py -e prod -s nswap.raffles > nswapraffles.log &
    nohup python manage.py -e prod -s nswap.detail > nswapdetail.log &
    nohup python manage.py -e prod -s monitor.run > monitor.log &
    nohup python manage.py -e prod -s monitor.twitterkol > monitortwitterkol.log &
    nohup python manage.py -e prod -s monitor.insightbot > monitorinsightbot.log &
    nohup python manage.py -e prod -s dappradar_daily.run > dappradar.log &
    nohup python3 manage.py -e prod -s mainex.playwright > mxplay.log &
    nohup python manage.py -e prod -s mainex.ccxt > mxccxt.log &
    nohup python manage.py -e prod -s monitor.process_error > monitorlogerror &"""


    key = 'processes'
    for row in content.strip().split('\n'):
        name = row.strip().split(' ')[6]
        print(name)
        redis_c.hset(key,name,1)
