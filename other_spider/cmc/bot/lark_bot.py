import os
import requests
import json
import logging
import time
from traceback import format_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Lark Push')

def sender(msg, url=None, title='cmc'):
    """
    # 文本格式化官方文档
    https://open.larksuite.com/document/ukTMukTMukTM/uMDMxEjLzATMx4yMwETM?lang=zh-CN
    :param url: webhook地址
    :param msg: 需要发送的消息
    :return:
    """
    if not url:
        # 默认报警链接，也支持传参
        url = os.getenv('LARK_WEBHOOK_CMC_6', '')
    msg_list = []
    for i in msg.strip().split('\n'):
        msg_row = [
            {
                "tag": "text",
                "text": i.strip()
            }
        ]
        msg_list.append(msg_row)


    data = {
        "email": os.getenv('LARK_MENTION_EMAIL', ''),
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": msg_list
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}
    num = 0
    while True:
        try:
            requests.request("POST", url, headers=headers, data=json.dumps(data))
            break
        except:
            logger.error(f'{data["name"]} 发送异常')
            logger.error(f'{data["name"]} {format_exc()}')
            logger.error(f'{data["name"]} 重试 {num} ...')
            time.sleep(10)
            num += 1
        # 重试不超过3次
        if num > 3:
            break