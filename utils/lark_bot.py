import os
import requests,json

def sender(msg, url=None, title='', del_blank_row=True):
    """
    # 文本格式化官方文档
    https://open.larksuite.com/document/ukTMukTMukTM/uMDMxEjLzATMx4yMwETM?lang=zh-CN
    :param url: webhook地址
    :param msg: 需要发送的消息
    """
    if not url:
        url = os.getenv('LARK_WEBHOOK_GENIIDATA_2', '')
    msg_list = []
    for i in msg.strip().split('\n'):
        i = i.strip()
        if del_blank_row:
            if not i:
                continue
        if i:
            i_list = i.split(' ')
            msg_row = []
            for i_word in i_list:
                if '&url&' in i_word:
                    href =  i_word.split('&url&')[-1].strip()
                    link_name = i_word.split('&url&')[0].strip()
                    item_json = {
                        "tag": "a",
                        "href": href,
                        "text": link_name
                    }
                else:
                    item_json = {
                        "tag": "text",
                        "text": i_word + ' '
                    }
                msg_row.append(item_json)
        else:
            msg_row = [{"tag": "text","text": "\n"}]
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
            print(res.text)
            return res.text
        except:
            num += 1
        if num > 3:
            break