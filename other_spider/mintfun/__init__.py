from .list import List
from .detail import Detail

def run(spider_name):
    if spider_name == 'list':
        List().run()
    else:
        Detail().run()