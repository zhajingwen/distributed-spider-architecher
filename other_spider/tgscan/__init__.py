import os
import logging
import time
from traceback import format_exc
from utils.lark_bot import sender


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project TGscan Run')

def error_alert(error_content):
    """启动失败告警"""
    web_hook_url = os.getenv('LARK_WEBHOOK_TGSCAN', '')
    content = f'紧急故障: {error_content}'
    sender(content, web_hook_url, 'tgscan')


def run(spider_name):
    """
    整个项目的启动入口
    """
    if spider_name == 'transfer':
        from other_spider.tgscan.utils.redis_data_transfer import Transfer
        Transfer().imigrate()
    elif spider_name == 'delamount':
        from other_spider.tgscan.user_balance_amount_manager.change_amount import Change
        Change().schedule()
    else:
        while True:
            try:
                from .entrance import entrance
                entrance(spider_name)
                break
            except Exception as e:
                error_content = format_exc()
                logger.error(f'启动失败，准备重试... 异常类型: {type(e).__name__}, 原因: {e}\n{error_content}')
                error_alert(error_content)
                time.sleep(3)
