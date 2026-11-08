import os
import json
import logging
import time
from threading import Thread
from flask import Flask, request, jsonify, abort
from .send_message import Send
from .gen_document import Spider
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BKproject Document Server')

app = Flask(__name__)
# 不同的应用不一样，存于事件回调菜单栏
token = os.getenv('LARK_VERIFY_TOKEN_BKPROJECT_DOCUMENT', '')

response_url = 'https://open.larksuite.com/open-apis/im/v1/messages'

def task(content, open_id, user_id):
    """
    处理爬虫任务，并且将结果返回给lark
    """
    logger.info(f'{content} 开始处理爬虫任务...')
    # 发送文件给用户
    Spider(open_id, user_id).run(content)

def repeat_quickly(open_id, msg=None):
    """
    快速响应
    """
    if not msg:
        msg = '查询中，请等待约3s...'
    Send().send(open_id, msg, 'text')

def check_content(open_id, content):
    """
    判断输入的指令是否合法
    """
    logger.info(f'收到消息：{content}')
    status = True
    if 'dextools.io/' not in content:
        status = False
    if 'pair-explorer' not in content:
        status = False
    if len(content) == 44 or len(content) == 42:
        status = True
    if not status:
        url = 'https://www.dextools.io/app/en/bnb/pair-explorer/0x429e89b78fc5249ddd5bc048c4d914ad720cf4e8'
        response_content = f'请输入dextool链接，比如：{url}'
        Send().send(open_id, response_content, 'text')
    return status

@app.route('/bkproject-document', methods=['GET', 'POST'])
def listen():
    content_type = request.headers.get('Content-Type')
    if request.method != 'POST':
        abort(403)
    if 'application/json' not in content_type:
        logger.info('request forbbiden application/json not in headers')
        abort(403)

    data = request.get_json()
    logger.info(f"origin data: {data}")
    challenge = data.get('challenge')
    # 验证（首次调用）
    if challenge:
        challenge = data['challenge']
        return jsonify({'challenge': challenge})
    # 正常对话
    else:
        header = data.get('header')
        event = data.get('event')
        if (not header) or (not event):
            logger.error('application/json not in headers')
            abort(403)
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
        message_id = message['message_id']
        create_time = int(int(event['message']['create_time'])/1000)
        # 1分钟之前的消息不做处理 （不知道怎么回事，会有好几个小时之前的消息，仍然在回调请求）
        if int(time.time()) - create_time > 60:
            logger.info('一分钟之前的消息，不做处理')
            return response
        user_id = event['sender']['sender_id']['user_id']
        open_id = event['sender']['sender_id']['open_id']
        # 提取消息内容
        content = message['content']
        try:
            content = json.loads(content)['text']
        except:
            # 快速响应
            t =  Thread(target=repeat_quickly,args=(open_id, '消息非法',))
            t.start()
            logger.warning('消息非法')
            return response
        content = content.strip()
        status = check_content(open_id, content)
        if status:
            redis_c = redis_cli()
            if redis_c.get(message_id):
                logger.info(f'{content} 该消息已经处理过了 {message_id}')
                return response
            # 快速响应
            t =  Thread(target=repeat_quickly,args=(open_id,))
            t.start()
            # 处理爬虫任务
            t =  Thread(target=task,args=(content, open_id, user_id,))
            t.start()
            # 添加到reids 设置过期时间3*60s，3*60s内不重复处理同一个消息（不可放于爬虫后，爬虫是耗时操作，在爬虫执行完之前会导致有去重空档）
            redis_c.set(message_id, 1, ex=3 * 60)
            # return response
        return response