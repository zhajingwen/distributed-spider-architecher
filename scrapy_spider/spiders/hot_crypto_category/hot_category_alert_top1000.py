# -*- coding: utf-8 -*-
import os
from scrapy_redis.spiders import RedisSpider
from utils.lark_bot import sender
from datetime import datetime

env = os.environ.get('env')

class HotCategory(RedisSpider):
    """
    top1000
    """
    name = 'hot_category_top1000'
    redis_key = f"{name}:start_url"
    change_ua = True
    start_urls = []

    def __init__(self, *args, **kwargs):
        super(HotCategory).__init__(*args, **kwargs)
        self.web_hook_api = os.getenv('LARK_WEBHOOK_HOT_CRYPTO_CATEGORY', '')

    def parse(self, response, **kwargs):
        """
        解析详情页，提取category
        """
        self.logger.info(f'Parse {response.url}')
        tags = response.xpath('//span[./text()="Tags"]/parent::div/following-sibling::div/div/span/a/text()').extract()
        if tags:
            self.logger.info(tags)
            tags = list(set(tags))
            # 统计数据
            alert_content = self.tags_amount(tags)
            if alert_content:
                # 在指定时间内发一次告警
                self.schedule(alert_content)

    def tags_amount(self, tags):
        """
        对板块进行计数统计并合成告警内容
        """
        # string类型的计数器
        for tag in tags:
            self.server.incr(f'{self.name}:tags:{tag}')
            num = int(self.server.get(f'{self.name}:tags:{tag}'))
            # 从string类型的计数器拿数据来刷新hash表
            self.server.hset(f'{self.name}:tags', tag, num)
        account_data = self.server.hgetall(f'{self.name}:tags')
        # 统计热门板块前10名
        sorted_values = list(reversed(sorted(account_data, key=lambda x: int(account_data[x]))))
        if len(sorted_values) < 3:
            return
        hot_category = ""
        # 输出排序后的结果, 热门板块前10
        for index, key in enumerate(sorted_values):
            if index > 9:
                break
            # 当天的热度统计值
            hot_index = int(account_data[key])
            # 与前一日热度值计算热度变化幅度
            lastday_hot_index = self.server.hget(f'{self.name}:tags:lastday', key)
            # 如果前一日有数据，那么就给告警内容增加变化幅度
            if lastday_hot_index:
                lastday_hot_index = int(lastday_hot_index)
                amplitude = int(((hot_index - lastday_hot_index)/lastday_hot_index)*100)
                content = f"板块：{key.decode()} 热度值：{hot_index} 变化：{amplitude}%\n"
            else:
                content = f"板块：{key.decode()} 热度值：{hot_index}\n"
            hot_category += content
        return hot_category

    def init_count_data(self):
        """
        初始化统计计数
        清除所有币 key
        清除存放所有币的包
        将当日的统计数据存档
        """
        # 每24小时初始化一次计数容器
        # 删除当日所有统计数据
        account_data = self.server.hgetall(f'{self.name}:tags')
        for key in account_data:
            self.server.delete(f'{self.name}:tags:{key}')
        self.server.delete(f'{self.name}:tags')
        # 将当日的统计数据放入lastday中
        for key in account_data:
            value = account_data[key]
            self.server.hset(f'{self.name}:tags:lastday', key, value)
        self.logger.info('计数器初始化成功')

    def alert(self, alert_content):
        """
        发送告警到lark 并 初始化计数器
        """
        # 防止在1小时内重复告警
        if not self.server.get(f'{self.name}:alterfilter'):
            # 推送时做记录，通过过期时间来告警去重
            self.server.setex(f'{self.name}:alterfilter', 5 * 60 * 60, 1)
            sender(alert_content, self.web_hook_api, '热门板块')
            # 初始化计数器
            self.init_count_data()

    def schedule(self, alert_content):
        """
        在指定时间推送告警
        """
        today_now = datetime.now()
        # 每日7-12点分执行
        today_at_07 = today_now.replace(hour=7, minute=0, second=0)
        today_at_12 = today_now.replace(hour=12, minute=0, second=0)
        # 指定在早上告警
        if today_at_07 < today_now < today_at_12:
            self.alert(alert_content)
        else:
            if env != 'prod':
                self.alert(alert_content)