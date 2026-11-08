# -*- coding: utf-8 -*-
import time
import datetime
import requests
# from kafka import KafkaProducer
from scrapy.crawler import logger
from utils.redisdb import redis_cli
from scrapy_spider.settings import *
import traceback


class KafkaPipelinePlus:
    # 获取生产者client
    def __init__(self):
        # bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS
        # kafka_args = KAFKA_ITEM_PRODUCER_PARAMS
        # self.producer = KafkaProducer(bootstrap_servers=bootstrap_servers, **kafka_args)
        self.redis_cli = redis_cli()
        # self.data_count_hour = {}
        # self.data_count_hour_history = {}
        self.headers = {"content-type": "application/json; charset=utf-8"}

    def process_item(self, item, spider):
        # 测试环境需要拼后缀 -daren_connect 其他环境拼 ‘’
        # 不转化成dict kafka会推送失败
        item = dict(item)
        # 指定爬虫不去重
        source_channel_id = hasattr(spider,'source_channel_id')
        if source_channel_id:
            item['source_channel_id'] = spider.source_channel_id
        # 数据结构按要求重新改造 2020.12.02
        if 'ext_fields' not in item:
            item['ext_fields'] = {
                'data_time':item['time'],
                'pop_type':item['pop_type'],
                'user_id':item['user_name'],
                'spider_time':int(time.time())
            }
        else:
            ext_fields = item['ext_fields']
            if 'data_time' not in ext_fields:
                ext_fields['data_time'] = item['time']
            if 'pop_type' not in ext_fields:
                ext_fields['pop_type'] = item['pop_type']
            if 'user_id' not in ext_fields:
                ext_fields['user_id'] = item['user_name']
            ext_fields['spider_time'] = int(time.time())
            item['ext_fields'] = ext_fields

        data_date = time.strftime("%Y%m%d", time.localtime(item['time']))
        # 如果指定日期，非指定日期的数据全部丢掉
        if spider_date != 'now' and data_date != spider_date:
            logger.info(f'非指定日期{spider_date}---丢弃{data_date}')
            return item
        # 去重
        if self.filter(spider,item,data_date):
            return item
        # 判断是否是历史数据并且优化time字段
        topic = self.judge_time(spider,item)

        # 统计采集量 需要在item 中time字段修改后统计
        field_date = datetime.datetime.now().strftime('%Y%m%d')
        # 防止死锁
        try:
            # 按规则统计爬到的量
            self.count_data(spider,field_date,item)
        except:
            traceback.print_exc()
            # 所有的统计操作做完解锁
            self.redis_cli.delete('lock')
        self.producer.send(topic, value=item)
        logger.info(f'kafka pushed {topic} successfully')
        item_info = item.get('user_name','') or item.get('pop_id')
        self.producer.flush()
        # 推送成功再写进去
        self.redis_cli.sadd(f'{spider.name}:itemsfilter',item['pop_id'])
        logger.info(f'用户：{item_info} 已采集')
        return item

    def filter(self,spider,item,data_date):
        """
        去重
        :param spider:
        :param item:
        :return:存在了就 过滤 返回True
        """
        # 重跑指定日期的数据不去重
        if data_date == spider_date:
            return False
        # 指定爬虫不去重
        filter_exsits = hasattr(spider,'filter')
        if filter_exsits:
            if not spider.filter:
                # 爬虫不去重
                return False
        # item通过md5去重  是否存在该id
        status = self.redis_cli.sismember(f'{spider.name}:itemsfilter',item['pop_id'])
        if status:
            return True
        else:
            return False

    def count_redis_db_init(self,item):
        """
        对redis统计结构数据初始化
        :param item:
        :return:
        """
        # 数据统计缓存在redis,考虑到容器分布式内存无法共享
        # 数据结构hash示例{'data_count_hour':{21：{1596006316：9999}，12：{1596006316：888}.'data_count_hour_history':{}}  存放所有渠道所有小时的数据
        data_count_hour = self.redis_cli.hget('data_count_hour_container', 'data_count_hour')
        if data_count_hour == b'null':
            data_count_hour = None
        if not data_count_hour:
            data_count_hour = {}
        else:
            data_count_hour = json.loads(data_count_hour)
        data_count_hour_history = self.redis_cli.hget('data_count_hour_container', 'data_count_hour_history')
        if data_count_hour_history == b'null':
            data_count_hour_history = None
        if not data_count_hour_history:
            data_count_hour_history = {}
        else:
            data_count_hour_history = json.loads(data_count_hour_history)
        source_channel_id = str(item['source_channel_id'])
        if source_channel_id not in data_count_hour:
            data_count_hour[source_channel_id] = {}
        if source_channel_id not in data_count_hour_history:
            data_count_hour_history[source_channel_id] = {}
        self.redis_cli.hset('data_count_hour_container', 'data_count_hour',json.dumps(data_count_hour))
        self.redis_cli.hset('data_count_hour_container', 'data_count_hour_history',json.dumps(data_count_hour_history))

    def count_data(self,spider,field_date,item):
        """
        统计爬虫采集到的数据量
        此时的item中time字段已经经过judge_time修改，符合数据实际推送的量，一致性
        :param spider:
        :param field_date:
        :param data_date:
        :param item:
        :return:
        """
        data_date = time.strftime("%Y%m%d", time.localtime(item['time']))
        # 判断是否统计过，统计过不再统计  统计到es
        if spider.name != 'bilibili_nxx':
            status = self.redis_cli.sismember(f'{spider.name}:itemsfilter',item['pop_id'])
            if status:
                # 必须放在上锁前，否则会死锁
                return
        # 拿不到锁则线程等待
        while True:
            # 循环刷新 acquire
            # 当一个线程读写数据库时，其他的不可以做读写
            acquire = self.redis_cli.setnx('lock', 1)
            if acquire:
                # 对锁加过期时间 100毫秒
                self.redis_cli.pexpire('lock', 100)
                break
            else:
                logger.warning('等待解锁')
                time.sleep(0.01)
        # 按小时统计
        # 指定爬虫不做小时统计
        count_hour_exsits = hasattr(spider,'count_hour')
        if count_hour_exsits:
            if spider.count_hour:
                self.count_hour(item, field_date, data_date, spider)
        else:
            self.count_hour(item, field_date, data_date, spider)
        # 按天统计
        if field_date == data_date:
            name = f'{spider.name}:count:today'
        else:
            name = f'{spider.name}:count:history'
        count = self.redis_cli.hget(name, field_date)
        if not count:
            count = 1
        else:
            count = int(count) + 1
        self.redis_cli.hset(name, field_date, count)
        # 所有的统计操作做完解锁
        self.redis_cli.delete('lock')

    def count_hour(self, item, field_date, data_date, spider):
        """
        按小时统计的总入口
        """
        # 初始化按小时统计redis数据库
        self.count_redis_db_init(item)
        # 当日数据统计
        data_count_hour = self.redis_cli.hget('data_count_hour_container', 'data_count_hour')
        data_count_hour = json.loads(data_count_hour)
        # 历史数据统计
        data_count_hour_history = self.redis_cli.hget('data_count_hour_container', 'data_count_hour_history')
        data_count_hour_history = json.loads(data_count_hour_history)

        if field_date == data_date:
            name = f'{spider.name}:count:today'
            # 小时统计
            bigcontainer_channel_id = self.count_data_per_hour(item,data_count_hour)
            hour_count_key = 'data_count_hour'
        else:
            name = f'{spider.name}:count:history'
            # 小时统计
            bigcontainer_channel_id = self.count_data_per_hour(item,data_count_hour_history)
            hour_count_key = 'data_count_hour_history'
        # 更新统计到redis
        self.redis_cli.hset('data_count_hour_container',hour_count_key,json.dumps(bigcontainer_channel_id))



    def count_data_per_hour(self,item,bigcontainer_channel_id):
        """
        按小时统计功能模块，将结果推送到api
        """
        # 本地开发不执行此统计
        if env == 'local':
            return bigcontainer_channel_id
        # 当前的小时时间
        data_now = datetime.datetime.now().strftime('%Y-%m-%d %H')
        timearray = time.strptime(data_now, "%Y-%m-%d %H")
        timestamp = str(int(time.mktime(timearray)))

        source_channel_id = str(item["source_channel_id"])
        small_container_timestamp = bigcontainer_channel_id[source_channel_id]
        # 下一个统计的时间节点，这个小时的key刚到来，从来没有在数据库出现过，则统计推送上个小时的累计数据
        if timestamp not in small_container_timestamp:
            last_timestamp = str(int(timestamp)-60*60)
            # 上一个统计周期完成，确保存在则推送到api   (这里并不是所有爬虫都会存在last_timestamp，假设爬虫并未采集到数据，那么连续几个小时都可能没有记录，他的统计结果将由其他爬虫代为完成)
            # 任何爬虫触发了这个条件都是将全部爬虫的小时统计结果推送到接口的
            if last_timestamp in small_container_timestamp:
                self.push_all_count(last_timestamp)
            # 为减少数据冗余，统计结果推送后重置统计空间
            # soure_channel_id下面的统计盒子
            small_container_timestamp = {}
            small_container_timestamp[timestamp] = 1
        else:
            small_container_timestamp[timestamp] = small_container_timestamp[timestamp] + 1
        # 累加采集量
        bigcontainer_channel_id[source_channel_id] = small_container_timestamp
        return bigcontainer_channel_id

    def push_all_count(self,last_timestamp):
        """
        上报
        同时推送历史统计和当天统计并且刷新 容器
        """
        # 单个小时只能有一个爬虫上报一次
        if self.redis_cli.exists('data_count_hour_pushstatus',last_timestamp):
            return
        else:
            self.redis_cli.delete('data_count_hour_pushstatus')
            self.redis_cli.sadd('data_count_hour_pushstatus',last_timestamp)
        # 当日数据统计
        data_count_hour = self.redis_cli.hget('data_count_hour_container', 'data_count_hour')
        bigcontainer_channel_id_today = json.loads(data_count_hour)
        # 历史数据统计
        data_count_hour_history = self.redis_cli.hget('data_count_hour_container', 'data_count_hour_history')
        bigcontainer_channel_id_history = json.loads(data_count_hour_history)
        for channel_id in bigcontainer_channel_id_today:
            try:
                channel_id_check = int(channel_id)
            except:
                logger.error(f'channel_id: {channel_id}')
                continue
            small_container_timestamp = bigcontainer_channel_id_today[channel_id]
            # 提取当日队列统计数据
            if last_timestamp in small_container_timestamp:
                count = small_container_timestamp[last_timestamp]
            else:
                count = 0
            # 提取历史统计数据
            if channel_id not in  bigcontainer_channel_id_history:
                bigcontainer_channel_id_history[channel_id] = {}
            if last_timestamp in bigcontainer_channel_id_history[channel_id]:
                historyCount = bigcontainer_channel_id_history[channel_id][last_timestamp]
            else:
                historyCount = 0
            # 构建数据结构
            form_data = {
                "sourceChannelId": int(channel_id),
                "timeHour": int(last_timestamp),
                "count": count,
                "historyCount": historyCount
            }
            form_data = json.dumps(form_data)
            response = requests.post(url=COUNT_API_PER_HOUR, data=form_data, headers=self.headers)
            logger.info(f'channel_id:{channel_id}小时统计状态---{response.json()["info"]}')

        # 更新redis hash数据
        self.redis_cli.hset('data_count_hour_container','data_count_hour',json.dumps(bigcontainer_channel_id_today))
        self.redis_cli.hset('data_count_hour_container','data_count_hour_history',json.dumps(bigcontainer_channel_id_history))

    def judge_time(self, spider, item):
        """
        无时间为设置为采集时间
        差值在10分钟以内不变
        差值大于10分钟小于1天，设置为采集时间
        采集时间和数据源发布时间差值大于1天，放入历史队列popinion-crawl-data-history
        :param spider:
        :param item:
        :return:
        """
        topic = spider.topic + TOPIC_EXTRA
        # settings接收命令传参
        if history_type == 'no':
            logger.info('不需要传入历史队列')
            return topic
        # 爬虫类属性定义是否需要传入历史队列
        if hasattr(spider,'history_type'):
            if not spider.history_type:
                return topic
        now = int(time.time())
        if not item['time']:
            item['time'] = now
        difference = now-item['time']
        if (difference < 24*60*60) and (difference>10*60):
            status = self.redis_cli.sismember(f'{spider.name}:itemsfilter', item['pop_id'])
            # 在不去重的前提下对已经采集过的信息，不再修改时间重复推送
            if not status:
                item['time'] = now
        if difference > 24*60*60:
            topic = HISTORY_TOPIC + TOPIC_EXTRA
        return topic