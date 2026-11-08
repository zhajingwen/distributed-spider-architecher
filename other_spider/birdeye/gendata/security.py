from curl_cffi import requests
import logging
from retry import retry
from utils.redisdb import redis_cli
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Birdeye Security')

class Security:
    def __init__(self):
        self.api_base = 'https://multichain-api.birdeye.so/solana/token/tokensecurity?token={}'
        self.redis_cli = redis_cli()
        self.redis_key = 'cloudflare:agentids'
        self.rds = DataUtils()

    @retry(tries=3, delay=10)
    def req(self, url):
        agent_id = self.redis_cli.spop(self.redis_key)
        logger.info(f'获取到agent-id: {agent_id}')
        headers = {
            "Agent-Id": agent_id,
            "Content-Type": "application/json",
            "Origin": "https://birdeye.so",
            "Page": "find_gems",
            "Referer": "https://birdeye.so/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        logger.info(f'Get: {agent_id}')
        res = requests.get(url, headers=headers, impersonate="chrome101")
        logger.info(f'Response {res.status_code}: {agent_id}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        else:
            # 如果ID能获取到正常数据，再塞回redis
            self.redis_cli.sadd(self.redis_key, agent_id)
        return res.json()

    def get_security_info(self, id):
        """
        拿到合约检测数据，返回文本结果
        """
        birdeye_token_api = self.api_base.format(id)
        data = self.req(birdeye_token_api)
        security_content = ''
        if data:
            try:
                data = data['data']['result']['data']
                # No
                mintable = data['mintable']
                if mintable:
                    security_content += 'mintable: Yes  '
                # No
                mutable_metadata = data['mutable_metadata']
                if mutable_metadata:
                    security_content += 'mutable_metadata: Yes  '
                # 是否放弃合约
                renounce = data['renounce']
                if renounce:
                    security_content += '放弃合约'
            except:
                logger.error(f'security 数据解析异常：{data}')
        return security_content
