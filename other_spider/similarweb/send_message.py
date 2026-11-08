import os
import requests
import json
import logging
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Similarweb Reapet')

class Send:
    def __init__(self):
        self.tenant_access_token_key = 'lark:similarweb:tenant_access_token'
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
            "app_id": os.getenv('LARK_APP_ID_SIMILARWEB', ''),
            "app_secret": os.getenv('LARK_APP_SECRET_SIMILARWEB', '')
        }
        res = requests.post(url, headers=headers, json=data)
        tenant_access_token = res.json()['tenant_access_token']
        # 记录redis 2小时的过期时间
        self.redis_cli.setex(self.tenant_access_token_key, 2*60*60-10, tenant_access_token)
        return tenant_access_token

    def send(self, receive_id, msg):
        url = "https://open.larksuite.com/open-apis/im/v1/messages"
        params = {"receive_id_type": "open_id"}
        # 格式化
        new_msg = ''
        for i in msg.strip().split('\n'):
            new_msg += (i + '\n')

        msgContent = {
            "text": new_msg,
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
        logger.info(response.headers['X-Tt-Logid'])  # for debug or oncall
        logger.info(response.content)  # logger.info Response
