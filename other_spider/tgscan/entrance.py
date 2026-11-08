import logging
import os
from other_spider.tgscan.utils.bot_register import TGBotRegister

env = os.environ.get('env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Entrance Of Bot')

def register(token, username):
    """
    注册机器人
    """
    TGBotRegister(username).main(token)


def entrance(spider_name):
    """
    入口 通过不同的参数启动不同的机器人
    """
    # 测试机器人
    if env != 'prod':
        logger.info('选择机器人：测试机器人')
        token = os.getenv('TG_BOT_TOKEN_TEST', '')
        # 绑定图片ID用
        username = os.getenv('TG_BOT_USERNAME_TEST', 'your_test_bot')
        register(token, username)
    # 生产机器人
    else:
        if spider_name == 'fuemosi':
            logger.info('选择机器人：fuemosi')
            token = os.getenv('TG_BOT_TOKEN_FUEMOSI', '')
            username = os.getenv('TG_BOT_USERNAME_FUEMOSI', 'your_bot')
            register(token, username)
        elif spider_name == 'kenan':
            logger.info('选择机器人：kenan')
            token = os.getenv('TG_BOT_TOKEN_KENAN', '')
            username = os.getenv('TG_BOT_USERNAME_KENAN', 'your_bot')
            register(token, username)
        else:
            logger.error(f'指令错误，无法启动任何机器人：{spider_name}')
