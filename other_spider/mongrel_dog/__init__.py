from .dexscreener.listpage import ListPage
from .gopluslabs import Spider
from .delete_junk_data import DeleteData

def run(spider_name):
    # 第1步
    if spider_name == 'list':
        ListPage().run()
    # 第3步，任务消费模式，依赖第2步
    elif spider_name == 'deldata':
        DeleteData().run()
    # 第2步，任务消费模式，依赖第1步 self.page_list_key = 'mongrel:dexscreener:pagelist'
    else:
        Spider().run()