from config.exchange import json_env
import requests
import logging
import time
import os
from functools import wraps
from traceback import format_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('INSIGHT BOT FORWARD')
env = os.environ.get('env')

class Forward:
    def __init__(self):
        # self.txt_url = ''
        self.base_url = 'https://api.telegram.org/bot' + os.getenv('TG_BOT_TOKEN_INSIGHT_TGBOT', '') + '/{}'
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        bot_token = os.getenv('TG_BOT_TOKEN_INSIGHT_TGBOT', '')

    def txt_msg(self, data, chat_id, message_thread_id, marketing_url):
        """
        send txt message
        """
        key = 'sendMessage'
        url = self.base_url.format(key)
        msg = f"{data['message']['text']}\n\n{os.getenv('INSIGHT_SIGNUP_TEXT', '')}\n✅ {marketing_url}"
        msg += os.getenv('INSIGHT_PROMO_LINE', '')
        pd = {
            "chat_id": chat_id,
            "parse_mode": "Markdown",
            "text": msg,
            "message_thread_id": message_thread_id,
            'disable_web_page_preview':True
        }
        # if message_thread_id is None pop the key
        if not message_thread_id:
            pd.pop('message_thread_id')
        res = requests.post(url, headers=self.headers, data=pd)
        logger.info(f'push to tg {res.text}')

    def photo_msg(self, data, chat_id, message_thread_id, marketing_url):
        """
        send photo message
        """
        key = 'sendPhoto'
        url = self.base_url.format(key)

        caption = f"{data['message'].get('caption','')}\n\n{os.getenv('INSIGHT_SIGNUP_TEXT', '')}\n✅ {marketing_url}"
        caption += os.getenv('INSIGHT_PROMO_LINE', '')
        caption_entities = data['message'].get('caption_entities')
        logger.info(f'photo list: {data["message"]["photo"]}')
        pd = {
            "chat_id": chat_id,
            "photo": data['message']['photo'][-1]['file_id'],
            "caption": caption,
            "caption_entities": caption_entities,
            # "parse_mode": 'HTML',
            "message_thread_id": message_thread_id,
        }
        # if message_thread_id is None pop the key
        if not message_thread_id:
            pd.pop('message_thread_id')
        if not caption_entities:
            pd.pop('caption_entities')
        res = requests.post(url, headers=self.headers, data=pd)
        logging.info(f'response code: {res.status_code} response: {res.text}')

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10

        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.error(f'{func.__name__}网络请求失败，重试...')
                        logger.error(format_exc())
                        retry_num += 1
                        if retry_num > num:
                            logger.error('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(20)
                return res

            return wrapper

        return recive_func

    @retry()
    def classification(self, data, chat_id, message_thread_id):
        """
        judge the recieve message type
        """
        # 格式: {"chat_id": "注册链接"}
        marketing_urls = json_env('INSIGHT_TG_MARKETING_URLS')
        marketing_url = marketing_urls[chat_id]
        if 'text' in data['message']:
            self.txt_msg(data, chat_id, message_thread_id, marketing_url)
        elif 'photo' in data['message']:
            self.photo_msg(data, chat_id, message_thread_id, marketing_url)
        else:
            logger.info(f'非正常消息：{data}')

    def all_channels(self, data):
        """
        发送到所有的目标频道
        """
        # 格式: {"chat_id": message_thread_id 或 null}
        if env == 'test':
            channels = json_env('INSIGHT_TG_CHANNELS_TEST')
        else:
            channels = json_env('INSIGHT_TG_CHANNELS')
        for chat_id in channels:
            message_thread_id = channels[chat_id]
            self.classification(data, chat_id, message_thread_id)
