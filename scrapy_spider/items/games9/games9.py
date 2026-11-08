from scrapy import Field
from scrapy_spider.items.base_items import BaseItem


class Item_games9(BaseItem):
    pub_info = Field()
    reply_info = Field()
    reply_reply_info = Field()


