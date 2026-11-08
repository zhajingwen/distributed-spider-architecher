# -*- coding: utf-8 -*-
from scrapy import Field, Item


class BaseItem(Item):
    """
    所有爬虫必须携带的字段
    """
    uuid = Field() # 数据唯一标识(md5值 32字符)
    spider_time = Field() #10位int时间戳 , 发布时间
    # pop_id = Field() # 渠道编号_md5
    # rating = Field()
    # url = Field()
    # user_name = Field()
    # content = Field()
    # data_url = Field()
    # pop_type = Field()
    # parent_id = Field()
    # post_id = Field()
    # game_id = Field()
    # parent_channel_type = Field()
    # child_channel_type = Field()
    # source_type = Field()
    # source_channel_id = Field()
    # ext_fields = Field()
    # title = Field()


