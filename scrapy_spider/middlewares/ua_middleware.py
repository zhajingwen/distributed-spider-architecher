# -*- coding: utf-8 -*-
# import random
import logging
# from scrapy_spider.settings import USER_AGENT_POOL
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('UA Middleware')

class RandomUserAgentMiddleware(object):
    """
    添加 UA 中间件
    也支持通过spider类属性来通知不加UA，比如：change_ua = False
    """
    ua = UserAgent()

    def process_request(self, request, spider):
        # scrapy网络框架会连接复用
        # scrapy为了提高速度多个请求复用握手连接，这就导致隧道模式无法切换IP
        # 通过下面的方式可以禁止复用连接
        # request.headers['Proxy-Connection'] = "close"
        request.headers["Connection"] = "close"

        # 为 True 则修改UA
        status = False
        change_ua = hasattr(spider,'change_ua')
        # 存在类属性，则根据属性值操作
        if change_ua:
            if spider.change_ua:
                status = True
        # 不存在类属性，则默认都加
        else:
            status = True
        if status:
            # ua = random.choice(USER_AGENT_POOL)
            random_user_agent = self.ua.random
            # print(random_user_agent)
            logger.info(f'UA choice: {random_user_agent}')
            request.headers["User-Agent"] = random_user_agent
