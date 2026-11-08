# -*- coding: utf-8 -*-
import time
import json
import logging
# import os
from datetime import datetime
from scrapy import signals
from scrapy.exceptions import NotConfigured
# from utils.parse_time import parse_time
from utils.redisdb import redis_cli
from config import env

# from scrapy_spider.settings import base_logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Extension')
# env = os.environ.get('env')
logger.info(f'extensions env: {env}')

# 原始配置参考https://scrapy-chs.readthedocs.io/zh_CN/0.24/topics/extensions.html
class SpiderInsertStartUrlExtension(object):
    """
    Scrapy所有爬虫实现定时调度的扩展
    """
    def __init__(self, item_count, crawler):
        """
        初始化操作
        :param item_count: 程序空闲的最大次数
        :param crawler: 类，用于发送关闭程序信号
        """
        self.crawler = crawler
        self.count = 0      # 统计空闲次数
        self.conn = redis_cli()

    @classmethod
    def from_crawler(cls, crawler):
        """
        必须方法
        """
        # 判断是否启用扩展
        if not crawler.settings.getbool('MYEXT_ENABLED'):
            raise NotConfigured
        # 每隔5个item 输出当前采集的数量
        item_count = crawler.settings.getint('MYEXT_ITEMCOUNT', 5)
        ext = cls(item_count, crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.spider_idle, signal=signals.spider_idle)  # 加载空闲信号
        return ext

    def cron_judgement(self,spider):
        """
        定时调度，比如在每日的8：00整调度，支持在spider中定义crontab的语法给变量
        比如每日0点1分启动：cron_job = "1 0 * * *"
        :return: True or False True则执行
        """
        # crontab的语法规则，该语法只约束启动时间，具体下次调度还得结合 schedule_time
        # 如果需要定时调度，则执行if语句
        cron_job = hasattr(spider,'cron_job')
        if cron_job:
            cron_job = spider.cron_job.split(' ')
            minute = cron_job[0]
            hour = cron_job[1]
            day = cron_job[2]
            month = cron_job[3]
            week = cron_job[4]
            now_minute = str(datetime.now().minute)
            now_hour = str(datetime.now().hour)
            now_day = str(datetime.now().day)
            now_month = str(datetime.now().month)
            now_week = str(datetime.now().weekday() + 1)
            if minute == '*':
                minute = now_minute
            if hour == '*':
                hour = now_hour
            if day == '*':
                day = now_day
            if month == '*':
                month = now_month
            if week == '*':
                week = now_week
            if (minute==now_minute)and(hour==now_hour)and(day==now_day)and(month==now_month)and(week==now_week):
                # 当cronjob定义的最小小单位为分钟级别时；爬虫可能在5秒跑完，那么1分钟内爬虫将有12次满足条件的情况，爬虫将被重复拉起12次
                # 为避免次情况的发生，通过redis key 在短时间内做去重
                if not self.conn.get(f"{spider.name}:spider_opened"):
                    self.conn.setex(f"{spider.name}:spider_opened",5*60,1)
                    return True
                else:
                    logger.info(f'{cron_job} 已经开始执行，由于爬虫速度过快，导致条件再次满足，故做去重处理')
                    return False
            else:
                logger.info(f'等待开始调度的时间 {cron_job}...')
                return False
        else:
            return False

    def interval_time(self,spider):
        """
        根据间隔时间调度 比如每30分钟调度一次: schedule_time = 12 * 30
        :return: True or False 真则执行
        """
        # 存在cron调度则不需要此间隔调度
        cron_job = hasattr(spider,'cron_job')
        schedule_time = hasattr(spider,'schedule_time')

        if cron_job:
            return False
        if not schedule_time:
            return False
        # 空闲超过指定时间
        if self.count > spider.schedule_time:
            self.count = 0
            return True
        else:
            return False

    def spider_opened(self, spider):
        """
        必须方法
        只执行一次，爬虫启动的时候执行
        支持指定时间启动
        """
        # 爬虫首次判断是否需要定时调度
        # 判断是否需要定时调度
        # 如果需要定时调度，则执行if语句
        cron_job = hasattr(spider,'cron_job')
        logger.info(f'环境： {env}')
        logger.info(f'cronjob: {cron_job}')
        # 线上环境才执行cron coinsadjust
        if env == 'prod':
            if cron_job:
                while True:
                    run = self.cron_judgement(spider)
                    if run:
                        break
                    else:
                        time.sleep(59)
        self.insert_start_url(spider, 'opened')
        logger.info("opened spider %s" % spider.name)
        # 该变量为了让程序idle的时候输出上次调度的时间，以此判断上次调度是否正常
        self.started_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def insert_start_url(self, spider, status):
        """
        将url插入redis队列
        """
        # 断点续爬(不做处理，engine会自动调用start_request方法进行处理)
        if self.conn.llen(spider.name + ":requests"):
            logger.info('断点续爬，继续未完成的任务队列...')
            return
        elif self.conn.llen(spider.redis_key):
            logger.info('启动任务队列已生成任务，准备开始...')
            return
        # 全新启动
        elif spider.start_urls:
            logger.info('任务队列为空，从 spider.start_urls 生成...')
            for url in spider.start_urls:
                data = json.dumps({"url":url})
                self.conn.lpush(spider.redis_key, data)
                logger.info(f"---insert start_url complete {url}")
        else:
            # 爬虫opened 不需要手动调用start_requests
            if status != 'opened':
                logger.info('从 start_request 类方法 直接生成任务...')
                return spider.start_requests()

    def spider_closed(self, spider):
        """
        必须方法
        """
        logger.info("closed spider %s" % spider.name)
        self.crawler.engine.close_spider(spider, '视频详细数据已经采集完毕')

    def spider_idle(self, spider):
        """
        记录信息，作出关闭选择
        框架默认5秒执行一次spider_idle
        :param spider:
        :return:
        """
        logger.info(f'{spider.name} Idle 爬虫上次启动时间为 {self.started_time}')
        # 判断redis_key中是否为空，如果为空时，则空闲一次，统计 + 1
        if not self.conn.llen(spider.name + ":requests") and not self.conn.llen(spider.redis_key):
            self.count += 1
            time.sleep(1)
        else:
            # 每次开始执行任务后，都初始化计数器，重新统计下一轮的空闲时长
            self.count = 0
        self.spider_run(spider)

    def spider_run(self,spider):
        """
        激活调度爬虫（往队列塞链接）
        需要根据条件判断是否激活
        """
        # 常规来讲，调度方式二选一
        cron = self.cron_judgement(spider)
        interval = self.interval_time(spider)
        if cron or interval:
            # 定时调度需要删除上一次请求产生的去重队列
            self.conn.delete(f'{spider.name}:dupefilter')
            # 删除有时间延迟
            time.sleep(3)
            logger.info("clear spider requests dupefilter completed ---- %s" % spider.name)
            self.insert_start_url(spider, 'idle')
            # logger.info(f'key: {spider.name}:starttime')
            # logger.info(f'starttime_parse: {parse_time(self.started_time)} self.started_time {self.started_time}')
            # 启动时间计入redis  方便分布式协调任务
            started_time_stamp = datetime.strptime(self.started_time, "%Y-%m-%d %H:%M:%S").timestamp()
            self.conn.set(f'{spider.name}:starttime', started_time_stamp)
            self.started_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
