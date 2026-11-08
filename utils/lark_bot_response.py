import requests
import json
import logging
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Lart BotSender')

class Send:
    def __init__(self, app_id, app_secret, project):
        self.tenant_access_token_key = f'lark:{project}:tenant_access_token'
        self.redis_cli = redis_cli()
        self.data = {
            "app_id": app_id,
            "app_secret": app_secret
        }

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
        res = requests.post(url, headers=headers, json=self.data)
        tenant_access_token = res.json()['tenant_access_token']
        # 记录redis 2小时的过期时间
        self.redis_cli.setex(self.tenant_access_token_key, 2*60*60-10, tenant_access_token)
        return tenant_access_token

    def send_text(self, receive_id, msg):
        """
        发送文本消息
        """
        # 格式化
        new_msg = ''
        for i in msg.strip().split('\n'):
            new_msg += (i + '\n')
        msgContent = {
            "text": new_msg,
        }
        data = {
            "receive_id": receive_id,  # open_id
            "msg_type": "text",
            "content": json.dumps(msgContent)
        }
        payload = json.dumps(data)
        return payload

    def send_file(self, receive_id, file_key, msg_type):
        """
        发送文件
        """
        if msg_type == 'file':
            content = {"file_key": file_key}
        else:
            content = {"image_key": file_key}
        data = {
            "receive_id": receive_id,
            "content": json.dumps(content),
            "msg_type": msg_type
        }
        payload = json.dumps(data)
        return payload

    def send(self, receive_id, msg, type):
        """
        回复消息
        """
        url = "https://open.larksuite.com/open-apis/im/v1/messages"
        params = {"receive_id_type": "open_id"}
        if type == 'text':
            payload = self.send_text(receive_id, msg)
        else:
            payload = self.send_file(receive_id, msg, type)
        tenant_access_token = self.gen_tenant_access_token()
        headers = {
            'Authorization': f'Bearer {tenant_access_token}',  # your access token
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, params=params, headers=headers, data=payload)
        logger.info(response.headers['X-Tt-Logid'])  # for debug or oncall
        logger.info(response.content)  # logger.info Response