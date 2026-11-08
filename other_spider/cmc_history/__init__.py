from .gen_seeds import gen
from .spider import Spider

def run(spider_name):
    if spider_name == 'gen':
        gen()
    else:
        Spider().consumer()
