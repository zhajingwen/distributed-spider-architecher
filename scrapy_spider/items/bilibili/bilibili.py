from scrapy import Field
from scrapy_spider.items.games9.games9 import Item_games9


class Item_bilibili(Item_games9):
    userinfo = Field()
    videoinfo = Field()
    replies = Field()

class Item_bilibili_official(Item_bilibili):
    up_count = Field()
    down_count = Field()
    user_level = Field()
    rating = Field()


