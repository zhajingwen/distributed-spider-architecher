from .listpage import List
from .detail import Detail
from .raffles import Raffles

def run(spider_name):
    if spider_name == 'list':
        List().run()
    elif spider_name == 'raffles':
        Raffles().run()
    else:
        Detail().run()
