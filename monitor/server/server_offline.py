import os
import time
import requests
import logging
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Server Live Status')

class PingDomain:
    """
    监控服务器是否存活
    """
    def __init__(self):
        self.url = 'https://example.com/#/login'
        self.lark_web_hook_api = os.getenv('LARK_WEBHOOK_SERVER', '')

    def req(self):
        """
        请求k8s接口，如果网络不同，那么说明服务器挂了
        """
        try:
            res = requests.get(self.url,timeout=5)
            logger.info(f'response code: {res.status_code}')
            if res.status_code != 200:
                logger.warning('服务器挂了')
                msg = f'服务器挂了 {res.status_code}'
                sender(msg, self.lark_web_hook_api, '紧急')
        except:
            logger.warning('服务器挂了')
            msg = '服务器挂了'
            sender(msg, self.lark_web_hook_api, '紧急')

    def monitor(self):
        """
        监控服务器是否存活
        每分钟扫一次
        """
        while True:
            self.req()
            time.sleep(60)
