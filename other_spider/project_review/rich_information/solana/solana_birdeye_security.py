from curl_cffi import requests
import logging
from retry import retry
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Birdeye Security Check')

class BirdeyeSecurity:
    """
    合约风险检测
    """
    def __init__(self):
        self.api_base = 'https://multichain-api.birdeye.so/solana/token/tokensecurity?token={}'
        self.redis_cli = redis_cli()
        self.redis_key = 'cloudflare:agentids'

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
        # res = requests.get(url, headers=headers)
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
                # Yes 是否放弃合约，
                renounce = data['renounce']
                if renounce:
                    security_content += '放弃合约'
                else:
                    security_content += '未放弃合约'
            except:
                logger.error(f'security 数据解析异常：{data}')
        if not security_content:
            security_content = '无'
        return security_content

    def check(self, data):
        """
        通过代币合约地址调用birdeye接口查询代币的合约风险检测结果
        """
        address = data['base_info']['代币地址']
        chain = data['base_info']['公链']
        # solana链的合约检测走birdeye
        if chain == 'solana':
            content = self.get_security_info(address)
            data['chain_data']['合约风险birdeye'] = content
            data['link']['birdeye'] = f'https://birdeye.so/token/{address}?chain=solana'
        return data