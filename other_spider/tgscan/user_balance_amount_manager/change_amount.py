import time
import redis
import os
import asyncio
import logging
from telegram import Bot
from other_spider.tgscan.utils.config.config import white_list, white_list_rediskey

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Balance amout reset')

env = os.environ.get('env')
if env == 'local':
    # host = '127.0.0.1'
    host = os.getenv('TGSCAN_REDIS_HOST', '')

else:
    # host = '<TGSCAN_REDIS_HOST>'
    host = '127.0.0.1'

token = os.getenv('TG_BOT_TOKEN_FUEMOSI', '')




class Change:
    def __init__(self):
        self.redis_cli = self.redis_cli()
        self.users_balance_key = 'tgscan:users:balance'
        self.threshold = 5

    def redis_cli(self):
        redis_conn = redis.StrictRedis(
            host=host,
            port=6379,
            # db=config.REDIS_DB,
            # username=config.REDIS_USERNAME,
            password=os.getenv('TGSCAN_REDIS_PASSWORD', ''),
            decode_responses=True,
            # ssl=True if env != 'pre' else False #aws用了ssl
        )
        return redis_conn

    async def set_menu_command(self, user_id):
        # user_id = 6938659213
        # user_id = 'kwloxd'
        bot = Bot(token=token)
        user = await bot.get_chat(user_id)
        return user.username


    def job(self):
        # 生成不删白名单
        self.white()
        data = self.redis_cli.hgetall(self.users_balance_key)
        # 将值从字符串转换为浮点数，并进行排序
        sorted_data = sorted(data.items(), key=lambda item: float(item[1]), reverse=True)
        num = 0
        num2 = 0
        num3 = 0
        for i in sorted_data:
            user_id = i[0]
            if int(user_id) in white_list:
                logger.info(f'白名单 {i} 不删')
                continue
            amount = float(i[1])
            # if amount > 0.2:
            #     num += 1
            #     num2 += 1
            #     username = asyncio.run(self.set_menu_command(user_id))
            #     print(f'余额重置, username: {username}, original data: {i}, reset amout to 0.1')
            #     self.redis_cli.hset(self.users_balance_key, user_id, 0.1)
            # if amount == 0.3:
            #     num2 += 1
            #     username = asyncio.run(self.set_menu_command(user_id))
            #     print(f'余额重置, username: {username}, original data: {i}, reset amout to 0.1')
            #     self.redis_cli.hset(self.users_balance_key, user_id, 0.1)
            # if amount > 0.3:
            #     num3 += 1
            #     username = asyncio.run(self.set_menu_command(user_id))
            #     print(f'余额重置, username: {username}, original data: {i}, reset amout to 0.1')
            #     self.redis_cli.hset(self.users_balance_key, user_id, 0.1)
            if amount > self.threshold:
                username = asyncio.run(self.set_menu_command(user_id))
                print(f'余额重置, username: {username}, original data: {i}, reset amout to 0.1')
                self.redis_cli.hset(self.users_balance_key, user_id, 0.1)

    def white(self):
        """
        生成白名单
        """
        white_list_redis = self.redis_cli.smembers(white_list_rediskey)
        for i in white_list_redis:
            white_list.append(int(i))
        return white_list


    def schedule(self):
        while True:
            self.job()
            # 每小时跑一次
            time.sleep(60*60)