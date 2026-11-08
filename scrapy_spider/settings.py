# -*- coding: utf-8 -*-
# 解决执行moudle报错的问题
import sys
import os
# 根据环境变量自动识别环境配置（线上或者线下）
from config import config
history_type = os.environ.get('history_type')
spider_date = os.environ.get('spider_date')
env = os.environ.get('env')
# 添加模块搜索路劲
sys.path.append('../scrapy_spider')
# redis 配置
REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_USERNAME = config.REDIS_USERNAME
REDIS_PASSWORD = config.REDIS_PASSWORD
REDIS_DB = config.REDIS_DB

# REDIS_URL = f'redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
# 启用TLS
REDIS_URL = f'rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
# 代理
PROXY_URL = config.PROXY_URL

BOT_NAME = 'cryptospider'

SPIDER_MODULES = ['scrapy_spider.spiders']
NEWSPIDER_MODULE = 'scrapy_spider.spiders'

# 小时粒度的去重有效期，即从0时刻开始,在每个n小时内相同的URL不再爬取,范围为1-23,超出范围则不设时间段去重
DUPLICATE_INVALID_MINUTE = -1

# UA池
USER_AGENT_POOL = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
]

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

CONCURRENT_REQUESTS = 3
# 禁止连接复用，下面两个参数得设置唯一；如果用隧道代理，这个必须配置
CONCURRENT_REQUESTS_PER_DOMAIN = 3
CONCURRENT_REQUESTS_PER_IP = 3

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 400, 403, 408, 404, 429]

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    # 'bh3_pb_spiders.middlewares.BaiduPbSpidersSpiderMiddleware': 543,
#     # splash配置
#     # 'scrapy_splash.SplashDeduplicateArgsMiddleware': 100,
# }

# 下载中间件 代理+UA+重试
DOWNLOADER_MIDDLEWARES = {
    "scrapy_spider.middlewares.ua_middleware.RandomUserAgentMiddleware": 100,
    "scrapy_spider.middlewares.proxy_middleware.ProxyMiddleware": 200,
    # 剔除请求头被自动添加的 Proxy-Authorization
    "scrapy_spider.middlewares.remove_proxy_authorizaton.RemoveProxyAuthMiddleware": 300,
    "scrapy_spider.middlewares.retry_middleware.RetryChangeProxy": 400,
    # 一般重定向要么是自己接口抓的不对，要么是出现了异常，无论哪种情况，自动重定向都不是一个好事
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
    # 启用自定义的重试中间件
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
}

# 启用自定义扩展
MYEXT_ENABLED = True
# 自定义定时调度
EXTENSIONS = {
   "scrapy_spider.extensions.extension.SpiderInsertStartUrlExtension": 100,
}

ITEM_PIPELINES = {
    # "scrapy_spider.pipelines.KafkaPipelinePlus":300,
    # "scrapy_spider.ext_pipelines.mongopipelines.MongodbPipeline": 400,
    # "scrapy_spider.ext_pipelines.test.Test": 500,
    "scrapy_spider.ext_pipelines.rds.MysqlPipeline": 100,
}


DOWNLOAD_FAIL_ON_DATALOSS = False

SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_QUEUE_CLASS = "scrapy_redis.queue.SpiderStack"

# 断点续爬
SCHEDULER_PERSIST = True
# 超时设置
DOWNLOAD_TIMEOUT = 10

# 去重字段，提供给pipline使用
ITEMS_DUPEFILTER_FIELDS = ['pop_id',"md5"]

# HTTP_PROXY = 'http://localhost:8888'
# HTTPS_PROXY = 'http://localhost:8888'

# 队列默认为list结构

