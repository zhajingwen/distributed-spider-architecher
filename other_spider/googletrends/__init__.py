# from .trends import Search
# from other_spider.googletrends_api.backup import Search
from .playwright_plan import SearchRelation as SearchRelationPlaywright
from .once import Play as PlayOnce

def run(spider_name):
    """
    nohup python manage.py -e prod -s googletrends.t > googletrends.log &
    """
    if spider_name == 'webkit' or spider_name == 'chronium':
        SearchRelationPlaywright(spider_name).run()
    else:
        PlayOnce().run()


