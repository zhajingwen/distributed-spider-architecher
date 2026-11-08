# from .trends import Search
from other_spider.googletrends_api.backup import Search
# from .playwright_plan import SearchRelation as SearchRelationPlaywright
from other_spider.googletrends_api.related_topics_and_queries import Search as SearchOnce

def run(spider_name):
    """
    nohup python manage.py -e prod -s googletrends.t > googletrends.log &
    """
    # if spider_name == 'playwright':
    #     SearchRelationPlaywright().run()
    # else:
    # if spider_name == 'once':
    #     SearchOnce().run()
    # else:
    Search().run()


