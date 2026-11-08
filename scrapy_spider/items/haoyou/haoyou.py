from scrapy import Field
from scrapy_spider.items.games9.games9 import Item_games9


class Item_haoyou(Item_games9):
    reply = Field()

