import json
import os
import re
import datetime
import time
import logging
import requests
from flask import Flask,request,jsonify
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from other_spider.qqgroup.webhook.config import *
from utils.pipelines import KafkaPipeline
from utils.redisdb import redis_cli
from other_spider.qqgroup.webhook.config import config


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('QQ Group Monitor')
redis_db_cli = redis_cli()
env = os.environ.get('env')


# 线程池
executor = ThreadPoolExecutor(20)
app = Flask(__name__)
kafkapipeline = KafkaPipeline()
TOPIC_EXTRA = config.TOPIC_EXTRA
topic = 'popinion-data-crawl-qq' + TOPIC_EXTRA
# 小时计数容器 包含两个channel_id
containers = {}
# 统计接口地址
COUNT_API_PER_HOUR = config.COUNT_API_PER_HOUR
# 接口请求头
headers = {"content-type": "application/json; charset=utf-8"}


@app.route('/', methods = ['GET','POST'])
def login():
    if request.method == 'GET':
        return 'QQ群消息接收转发服务（推送到Kafka）'
    elif request.method == 'POST':
        executor.submit(kafka_task,(json.loads(request.data)))
        return jsonify({'status':'success'})

def kafka_task(data):
    """
    将接收的消息推送到kafka队列
    :param data: dict 最新消息的json体
    :return:
    """
    for filter in filters:
        if filter in data['message']:
            logger.info(f'特殊信息过滤...{data}')
            return
    data = cut_emoji(data)
    if not data:
        return
    if data['group_id'] in nxx_group_list:
        channel_id = 31
        channel_name = 'nxxqqgroup'
        game_id = 4
    elif data['group_id'] in ys_group_list:
        channel_id = 54
        channel_name = 'ysqqgroup'
        game_id = 2
    elif data['group_id'] in yunyx_group_list:
        channel_id = 59
        channel_name = 'yunyxqqgroup'
        game_id = 0
    elif data['group_id'] in miyoushe_kol:
        channel_id = 35
        channel_name = 'myskolqqgroup'
        game_id = 0
    else:
        channel_id = 16
        channel_name = 'bh3qqgroup'
        game_id = 1
    # 时间戳如果非10位，转成10位
    data_time = str(data['time'])
    if len(data_time) > 10:
        data_time = data_time[:-3]
    data_time = int(data_time)

    # 群号发消息QQ号+时间戳去重，避免不同QQ程序采集到的数据重复
    uuid = md5(f'{data["group_id"]}{data["sender"]["user_id"]}{data_time}'.encode()).hexdigest()

    data['data_time'] = data_time
    data['pop_type'] = 0
    data['user_id'] = data["sender"]["user_id"]
    data['main_post_id'] = uuid

    # 数据去重
    if filter_data(uuid):
        return
    item = {
        'time':data_time,
        'user_name': data['sender']['nickname'],
        'content': data['message'],
        'pop_id': f'00{channel_id}_{uuid}',
        'url': '',
        'pop_type': 0,
        'parent_id': '',
        'post_id': uuid,
        'game_id': game_id,
        'parent_channel_type': 9,
        'child_channel_type': '9-1',
        'source_type': '1',
        'source_channel_id': channel_id,
        'ext_fields': data,  # 需求方要求保留：如果可以都保留吧， 不敢保证后续业务会不会突然用得上...
        'title': '',
    }
    kafkapipeline.process_item(item,topic)
    # 数据统计
    count_data(channel_name,item)

def cut_emoji(data):
    """
    剔除表情
    """
    # \[CQ:image,.+?\]
    # [CQ:xml,data=<?xml version=\'1.0\' encoding=\'UTF-8\' standalone=\'yes\'?><msg templateID="123" url="https://www.baidu.com/s?ie=UTF-8&amp;amp;wd=re.sub" serviceID="33" action="web" actionData="" brief="【链接】re.sub_百度搜索" flag="8"><item layout="2"><picture cover="https://tangram-1251316161.file.myqcloud.com/files/20201102/1236dba9e0a258b779fa3c6ad6e5fff1.png"/><title>re.sub_百度搜索</title><summary></summary></item></msg>]
    re_pattern = '\[CQ:.+?\]'
    # 剔除表情 和 图片
    if '[CQ:' in data['message']:
        message = data['message']
        content = re.sub(re_pattern,'',message)
        if not content:
            logger.info(f'全部都是表情，过滤 {message}')
            return
        data['message'] = content
    return data

def filter_data(uuid):
    """
    根据UUID去重
    """
    # # item通过md5去重  是否存在该id
    # status = redis_db_cli.sismember(f'qqgroup:itemsfilter',uuid)
    # if status:
    #     return True
    # else:
    #     redis_db_cli.sadd(f'qqgroup:itemsfilter', uuid)
    #     return False
    return False

def count_data(channel_name,item):
    """
    按天统计和按小时统计
    :param channel_name:
    :param item:
    :return:
    """
    # 按天统计
    # 对hook到的消息数量做统计
    field_date = datetime.datetime.now().strftime('%Y%m%d')
    count = redis_db_cli.hget(f'{channel_name}:count',field_date)
    if not count:
        count = 1
    else:
        count = int(count)+1
    redis_db_cli.hset(f'{channel_name}:count',field_date,count)
    logger.info(f"当日采集---{count}")

    # 按小时统计，将结果推送到api
    # 本地开发不执行此统计
    if env == 'local':
        return
    data_now = datetime.datetime.now().strftime('%Y-%m-%d %H')
    timearray = time.strptime(data_now, "%Y-%m-%d %H")
    timestamp = time.mktime(timearray)
    source_channel_id = item['source_channel_id']
    if source_channel_id in containers:
        container = containers[source_channel_id]
    else:
        container = {}
    # 下一个统计的时间节点
    if timestamp not in container:
        container[timestamp] = 1
        last_timestamp = timestamp - 60 * 60
        # 上一个统计周期完成，确保存在则推送到api
        if last_timestamp in container:
            count = container[last_timestamp]
            logger.info(f"上小时{last_timestamp}采集---{count}")
            # 构建数据结构
            form_data = {
                "sourceChannelId": item["source_channel_id"],
                "timeHour": last_timestamp,
                "count": count,
                "historyCount": 0
            }
            form_data = json.dumps(form_data)
            response = requests.post(url=COUNT_API_PER_HOUR, data=form_data, headers=headers)
            logger.info(f'小时统计状态---{response.json()["info"]}')
            # 为防止内存溢出和重复推送，统计结果推送后将上一个周期的记录删除
            container.pop(last_timestamp)
    else:
        container[timestamp] = container[timestamp] + 1
    containers[source_channel_id] = container



if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5003)