import os
import json
import logging
import time
from threading import Thread
from traceback import format_exc
from flask import Flask, request, jsonify, abort
from .send_message import Send
from .spider import Spider
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BK Spider Event Handler')

app = Flask(__name__)
# lark 机器人验证token
token = os.getenv('LARK_VERIFY_TOKEN_BK_EARLY_PROJECT', '')
response_url = 'https://open.larksuite.com/open-apis/im/v1/messages'

def task(content, open_id, message_id):
    """
    处理爬虫任务，并且将结果返回给lark
    """
    redis_c = redis_cli()
    if redis_c.get(message_id):
        logger.info(f'{content} 该消息已经处理过了 {message_id}')
        return
    # 添加到reids 设置过期时间3*60s，3*660s内不重复处理同一个消息（不可放于爬虫后，爬虫是耗时操作，在爬虫执行完之前会导致有去重空档）
    redis_c.set(message_id,1,ex=3*60)
    logger.info(f'{content} 开始处理爬虫任务...')
    try:
        # 获取到 币相关信息
        res_content = Spider().search(content)
    except:
        res_content = format_exc()
    Send().send(open_id, res_content)

def repeat_quickly(open_id):
    # 快速响应
    Send().send(open_id, '查询中，请等待约3s...')

@app.route('/lark', methods=['GET', 'POST'])
def hello_world():
    content_type = request.headers.get('Content-Type')
    if request.method != 'POST':
        abort(403)
    if 'application/json' not in content_type:
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
        message_id = event['message']['message_id']
        create_time = int(int(event['message']['create_time'])/1000)
        # 1分钟之前的消息不做处理 （不知道怎么回事，会有好几个小时之前的消息，仍然在回调请求）
        if int(time.time()) - create_time > 60:
            return response
        # 提取消息内容
        content = event['message']['content']
        content = json.loads(content)['text']
        content = content.strip()
        open_id = event['sender']['sender_id']['open_id']
        # 快速响应
        t =  Thread(target=repeat_quickly,args=(open_id,))
        t.start()
        # 处理爬虫任务
        t =  Thread(target=task,args=(content, open_id, message_id,))
        t.start()
        return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=84)