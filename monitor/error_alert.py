import os
import logging
import time
from hashlib import md5
from other_spider.cmc.bot.lark_bot import sender
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Error Alert')


def alert(msg, redis_cli, error_type):
    web_hook_api = os.getenv('LARK_WEBHOOK_ALERT', '')
    while True:
        try:
            uid = md5(msg.encode()).hexdigest()
            key = f'monitor:{uid}'
            # 1小时内没报过相同的警再报警
            status = redis_cli.get(key)
            if not status:
                sender(msg, web_hook_api, error_type)
                # 每小时相同的告警只推送一次，防止疯狂推送
                redis_cli.setex(key,60*60,1)
            break
        except:
            logger.warning('发送异常')
            time.sleep(10)