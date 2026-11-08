import logging
from utils.redisdb import redis_cli
from .marketshare import function_router as msfunction_router
from utils.lark_bot_response import Send
from other_spider.input_hub.config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Router')

class Router:
    """
    路由指令 拿到返回值
    响应用户消息
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.jobs_key = 'mainexmarketpercent:jobs'
        self.send = Send(app_id, app_secret, app_name)

    def reply(self, exe_response, open_id):
        """
        响应客户信息
        """
        self.send.send(open_id, exe_response, 'text')

    def router(self, message, open_id):
        """
        指令识别并分类
        """
        cmd = message.strip()
        # 目前只有Marketshare项目，故交给该项目做function路由处理
        exe_response = msfunction_router(cmd)
        self.reply(exe_response, open_id)