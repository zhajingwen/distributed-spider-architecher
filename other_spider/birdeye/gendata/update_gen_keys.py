import os
import random
import json
import time
import requests
import logging
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gen Update AgentID')

class GenKeys:
    def __init__(self):
        """
        生成 Agent-Id  该ID并不与IP和useragent 绑定
        依赖于老ID来刷新新的ID，但是老ID并不会因此而失效，也没有过期时间
        """
        # Change keys if needed
        # 多个 key 用逗号分隔
        self.keys = [k for k in os.getenv('BIRDEYE_AGENT_KEYS', '').split(',') if k]
        self.headers = {
            'CF-Client-Version': 'a-6.11-2223',
            'Host': 'api.cloudflareclient.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/3.12.1'
        }
        self.redis_key = 'cloudflare:agentids'
        self.redis_cli = redis_cli()

    async def getKey(self, key):
        url = 'https://api.cloudflareclient.com/v0a2223/reg'
        url2 = 'https://api.cloudflareclient.com/v0a2223/reg/'
        r1 = await self.fetch(url, {
            'method': 'POST',
            'headers': self.headers
        })
        json1 = r1.json()
        id = json1['id']
        license = json1['account']['license']
        token = json1['token']

        r2 = await self.fetch(url, {
            'method': 'POST',
            'headers': self.headers
        })
        json2 = r2.json()
        id2 = json2['id']
        token2 = json2['token']

        headersGet = { 'Authorization': 'Bearer ' + token, **self.headers }
        headersGet2 = { 'Authorization': 'Bearer ' + token2, **self.headers }
        headersPost = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Authorization': 'Bearer ' + token,
            **self.headers
        }

        patchJson = { 'referrer': id2 }
        await self.fetch(url2 + id, {
            'method': 'PATCH',
            'headers': headersPost,
            'body': json.dumps(patchJson)
        })

        await self.fetch(url2 + id2, {
            'method': 'DELETE',
            'headers': headersGet2
        })

        putJson1 = { 'license': key }
        await self.fetch(url2 + id + '/account', {
            'method': 'PUT',
            'headers': headersPost,
            'body': json.dumps(putJson1)
        })

        putJson2 = { 'license': license }
        await self.fetch(url2 + id + '/account', {
            'method': 'PUT',
            'headers': headersPost,
            'body': json.dumps(putJson2)
        })

        r3 = await self.fetch(url2 + id + '/account', {
            'method': 'GET',
            'headers': headersGet
        })
        json3 = r3.json()
        accountType = json3['account_type']
        referralCount = json3['referral_count']
        updatedLicense = json3['license']

        await self.fetch(url2 + id, {
            'method': 'DELETE',
            'headers': headersGet
        })

        return updatedLicense

    async def fetch(self, url, options):
        response = requests.request(options['method'], url, headers=options['headers'], data=options.get('body'))
        return response

    async def main(self, oldkey):
        """
        将生成的AgentID 塞入redis
        """
        # 通过老key生成新key
        key = await self.getKey(oldkey)
        self.redis_cli.sadd(self.redis_key, key)
        logger.info(f'AgentID 已写入redis：{key}')

    async def run(self):
        """
        启动刷新Agent-Id的常驻程序
        """
        while True:
            key = self.redis_cli.spop(self.redis_key)
            if not key:
                key = random.choice(self.keys)
            logger.info(f'刷新：{key}')
            await self.main(key)
            # 取出来后再塞进去
            self.redis_cli.sadd(self.redis_key, key)
            time.sleep(60*60)