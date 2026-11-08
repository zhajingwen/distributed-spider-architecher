import importlib
from scrapy.cmdline import execute

__all__ = ['run_spider']


def run_spider(cmd):
    cmds = cmd.split('.')
    spider_project = cmds[0]
    spider_name = cmds[1]
    if spider_project == 'scrapy':
        execute(['scrapy', 'crawl', f'{spider_name}'])
    else:
        if spider_project == 'monitor':
            spider = importlib.import_module('monitor')
        else:
            spider = importlib.import_module(f'other_spider.{spider_project}')
        spider.run(spider_name)
