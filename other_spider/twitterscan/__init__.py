from .twitterscan import Spider
# from .test import Test
from .trendx_alert import TrendxAlert
from .trendx_insert import TrendxInsert
def run(spider_name):
    """
    nohup python manage.py -e prod -s twitterscan.run > twitterscan.log &
    """
    if spider_name == 'alert':
        TrendxAlert().run()
    # elif spider_name == 'rerun':
    #     Spider().rerun()
    else:
        # Spider().run()
        TrendxInsert().run()
