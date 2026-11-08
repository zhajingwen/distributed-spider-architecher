import json
import logging
import time
from threading import Thread
from flask import Flask, request, jsonify, abort
from utils.lark_bot_response import Send
from utils.redisdb import redis_cli
from .verify import match_verify
from other_spider.btc_gas.gen_data.load_send_graph import LoadData
from other_spider.btc_gas.config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BTC GAS Server')

app = Flask(__name__)
response_url = 'https://open.larksuite.com/open-apis/im/v1/messages'

def task(message, open_id, message_id):
    """
    生成这些图返回
    """
    redis_c = redis_cli()
    if redis_c.get(message_id):
        logger.info(f'{message} 该消息已经处理过了 {message_id}')
        return
    # 添加到reids 设置过期时间3*60s，3*660s内不重复处理同一个消息（不可放于爬虫后，爬虫是耗时操作，在爬虫执行完之前会导致有去重空档）
    redis_c.set(message_id,1,ex=3*60)
    logger.info(f'开始图片任务...')
    LoadData(message).cmd_process(open_id)

def repeat_quickly(open_id, message_id):
    """
    快速给用户反馈
    """
    # 过滤重复的消息事件
    redis_c = redis_cli()
    if redis_c.get(message_id):
        return
    Send(app_id, app_secret, app).send(open_id, '正在生成，请等待约2s...', 'text')

@app.route('/btc-gas', methods=['GET', 'POST'])
def listen():
    # 判断请求是否是属于配对校验的请求
    match_status = match_verify(request)
    if match_status:
        return match_status

    content_type = request.headers.get('Content-Type')
    if request.method != 'POST':
        abort(403)
    if 'application/json' not in content_type:
        abort(403)

    data = request.get_json()
    logger.info(f"origin data: {data}")
    header = data.get('header')
    event = data.get('event')
    if (not header) or (not event):
        abort(403)
    # 每一次消息推送都会携带Token进行鉴权
    token_recieved = header.get('token')
    if not token_recieved:
        abort(403)
    if token_recieved != token:
        abort(403)
    message = event.get('message')
    if not message:
        abort(403)
    response_body = {'message': 'success'}
    response = jsonify(response_body)
    response.status_code = 200

    # 过滤消息
    message_id = event['message']['message_id']
    create_time = int(int(event['message']['create_time'])/1000)
    # 1分钟之前的消息不做处理 （不知道怎么回事，会有好几个小时之前的消息，仍然在回调请求）
    if int(time.time()) - create_time > 60:
        logger.info('一分钟之前的消息，不做处理')
        return response
    # 提取消息内容
    content = event['message']['content']
    content = json.loads(content)['text']
    message = content.strip()
    open_id = event['sender']['sender_id']['open_id']
    # 快速响应
    t =  Thread(target=repeat_quickly,args=(open_id,message_id,))
    t.start()
    # 处理图表绘制任务
    t =  Thread(target=task,args=(message, open_id, message_id,))
    t.start()
    return response