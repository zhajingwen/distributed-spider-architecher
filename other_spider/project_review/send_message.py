import os
import requests
import json
import logging
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review Reapet')

class Send:
    def __init__(self):
        self.tenant_access_token_key = 'lark:projectreview:tenant_access_token'
        self.redis_cli = redis_cli()

    def gen_tenant_access_token(self):
        """
        获取 tenant_access_token
        """
        # redis缓存的没过期，直接返回
        tenant_access_token = self.redis_cli.get(self.tenant_access_token_key)
        if tenant_access_token:
            return tenant_access_token
        url = 'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal'
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        data = {
            "app_id": os.getenv('LARK_APP_ID_PROJECT_REVIEW', ''),
            "app_secret": os.getenv('LARK_APP_SECRET_PROJECT_REVIEW', '')
        }
        res = requests.post(url, headers=headers, json=data)
        tenant_access_token = res.json()['tenant_access_token']
        # 记录redis 2小时的过期时间
        self.redis_cli.setex(self.tenant_access_token_key, 2*60*60-10, tenant_access_token)
        return tenant_access_token


    def split_msg(self, msg):
        """
        lark单次支持的文本长度有限，需要进行切割
        """
        rows = msg.split('\n')
        length = len(rows)
        content1 = '\n'.join(rows[:int(length/2)])
        content2 = '\n'.join(rows[int(length/2):])
        return [content1, content2]

    def send_once(self, receive_id, msg):
        url = "https://open.larksuite.com/open-apis/im/v1/messages"
        params = {"receive_id_type": "open_id"}
        msgContent = {
            # "tag": "lark_md",
            "text": msg,
        }
        req = {
            "receive_id": receive_id,  # open_id
            "msg_type": "text",
            "content": json.dumps(msgContent)
        }
        payload = json.dumps(req)
        tenant_access_token = self.gen_tenant_access_token()
        headers = {
            'Authorization': f'Bearer {tenant_access_token}',  # your access token
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, params=params, headers=headers, data=payload)
        logger.info(f"lark send response X-Tt-Logid: {response.headers['X-Tt-Logid']}")  # for debug or oncall
        logger.info(f"lark send response: {response.content}")  # for debug or oncall

    def send(self, receive_id, msg):
        """
        将原始消息切割成两块，分两次发送
        """
        self.send_once(receive_id, msg)
        # msgs = self.split_msg(msg)
        # for m in msgs:
        #     self.send_once(receive_id, m)