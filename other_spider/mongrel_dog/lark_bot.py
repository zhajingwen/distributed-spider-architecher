import os
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Lark Bot')

def sender(msg, url=None, title='dexscreener'):
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
    for index, i in enumerate(msg.strip().split('\n')):
        if 'http' in i:
            name = i.split('：')[0].strip()
            href = i.split('：')[1]

            msg_row = [
                {
                    "tag": "text",
                    "text": name.split('、 ')[0] + '、 ',
                },
                {
                    "tag": "a",
                    "text": name.split('、 ')[1],
                    'href': href
                }
            ]
        else:
            msg_row = [
                {
                    "tag": "text",
                    "text": i.strip()
                }
            ]
        double_space = {
            "tag": "text",
            "text": '  '
        }
        if index > 0:
            msg_row.insert(0,double_space)
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
            res = requests.request("POST", url, headers=headers, data=json.dumps(data))
            logger.info(f'lark 推送结果：{res.text}')
            break
        except:
            num += 1
        if num > 3:
            logger.info(f'lark 推送失败：{msg}')
            break