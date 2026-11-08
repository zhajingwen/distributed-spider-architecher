from .list_page import GemList
from .detail import Detail
from .free_mint import PushAllData
def run(spider_name):
    """
    nohup python manage.py -e prod -s gem.list > gemlist.log &
    nohup python manage.py -e prod -s gem.list1h > gemlist1h.log &
    nohup python manage.py -e prod -s gem.list15m > gemlist15m.log &
    nohup python manage.py -e prod -s gem.list24h > gemlist24h.log &
    nohup python manage.py -e prod -s gem.freemint > gemfreemint.log &
    nohup python manage.py -e prod -s gem.detail > gemdetial.log &
    """
    if 'list' in spider_name:
        if '1h' in spider_name:
            duration = '?duration=1_hour'
        elif '15m' in spider_name:
            duration = '?duration=15_mins'
        elif '24h' in spider_name:
            duration = '?duration=24_hours'
        else:
            duration = ''
        GemList(duration).run()
    elif 'freemint' in spider_name:
        PushAllData().consumer_redis()
    else:
        Detail().consumer()
