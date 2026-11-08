# -*- coding: utf-8 -*-
# from scrapy.crawler import logger
import logging
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Proxy Middleware')

class ProxyMiddleware(object):
    """
    支持通过Spider 类属性'proxy'来指定是否走代理
    proxy 为 False 不走代理
    没有该属性或者为True 则走代理
    """
    def __init__(self):
        # 代理 luminati
        self.proxy = config.PROXY_URL

    def process_request(self, request, spider):
        """
        添加代理
        只有spider类属性'proxy'为False才不添加，比如：proxy = False
        """
        # 是否启用代理
        proxy_status = hasattr(spider,'proxy')
        if proxy_status:
            if not spider.proxy:
                return
                # 可以通过爬虫类属性修改proxy
            if 'http://' in spider.proxy:
                request.meta["proxy"] = spider.proxy
        else:
            # 直接代理  来自baseconfig
            request.meta["proxy"] =  self.proxy
        logger.info(f"代理请求:-->{request._url}")
        # scrapy网络框架会连接复用
        # scrapy为了提高速度多个请求复用握手连接，这就导致隧道模式无法切换IP
        # 通过下面的方式可以禁止复用连接
        # request.headers['Proxy-Connection'] = "close"
        request.headers["Connection"] = "close"


