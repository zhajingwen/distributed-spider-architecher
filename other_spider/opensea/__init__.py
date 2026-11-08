from .mint import OpenseaList
from .pending import OpenseaPending
from .detail import DetailPending

def run(spider_name):
    if spider_name == 'list':
        OpenseaList().run()
    elif spider_name == 'pending':
        OpenseaPending().run()
    else:
        DetailPending().run()