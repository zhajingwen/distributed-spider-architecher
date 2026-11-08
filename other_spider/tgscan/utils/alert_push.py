import os
import logging
import requests,json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Alert TO Feishu')

async def sender(msg, url=None, title='TGSCAN'):
    """
    # 文本格式化官方文档
    https://open.larksuite.com/document/ukTMukTMukTM/uMDMxEjLzATMx4yMwETM?lang=zh-CN
    :param url: webhook地址
    :param msg: 需要发送的消息
    :return:
    """
    if not url:
        # 默认报警链接，也支持传参
        url = os.getenv('LARK_WEBHOOK_FEISHU_ALERT', '')
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
        # "email": "<LARK_MENTION_EMAIL>",
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
            num += 1
        if num > 3:
            logger.error(f'飞书消息推送失败：{msg}')
            break