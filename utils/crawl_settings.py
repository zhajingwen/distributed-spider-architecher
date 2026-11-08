from scrapy.settings import Settings
from scrapy.crawler import CrawlerProcess


__all__ = [
    'get_project_settings', 'get_crawler_process'
]

def get_project_settings():
    settings = Settings()
    settings.setmodule('scrapy_spider.settings', priority='project')
    return settings


def get_crawler_process():
    process = CrawlerProcess(settings=get_project_settings())
    return process