import logging
from hashlib import md5
from datetime import datetime, time, timedelta
from utils.rds import DataUtils
from other_spider.mainex_marketpercent_bot.gen_data.gen_upload_file import GenFileId
from utils.lark_bot_response import Send
from other_spider.mainex_marketpercent_bot.config import *
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Deal With CMD')

class LoadData:
    def __init__(self, message):
        self.cmd = self.cmd_format(message)
        self.rds = DataUtils()
        self.send = Send(app_id, app_secret, app_name)
        self.redis_cli = redis_cli()
        self.redis_jobkey = 'marketsharebot:coinsadjust:{}'

    def gen_job_id(self):
        """
        生成 一个查询区间的任务ID，为了不重复上传图片，节省时间
        """
        current_time = datetime.now().time()
        target_time = time(8, 30)  # 设置目标时间为当日的8点30

        if current_time > target_time:
            # 获取当日0点的时间戳
            timestamp = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        else:
            yesterday_date = (datetime.now() - timedelta(days=1))
            # 获取昨日日0点的时间戳
            timestamp = int(yesterday_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        uuid_content = f'{timestamp}&{self.cmd}'
        id = md5(f'{uuid_content}'.encode('utf-8')).hexdigest()
        return id

    def cmd_format(self, message):
        """
        对指令进行格式化处理
        """
        message = message.strip()
        if '/' in message:
            try:
                keyword = message.split('/')[0]
                time_date = message.split('/')[1]
                time_date = int(time_date)
                return keyword, time_date
            except:
                logger.info(f'指令错误：{message}')
                return
        else:
            logger.info(f'指令错误：{message}')
            return


    def select_data(self, open_id):
        """
        根据指令从数据库加载数据 + 将数据转换为csv文件发送给用户
        """
        # 任务ID
        id = self.gen_job_id()
        # 先看redis是否已经存在该任务ID，如果存在就不需要重复执行任务，直接从redis拿到image_key
        redis_key = self.redis_jobkey.format(id)
        image_keys = self.redis_cli.get(redis_key)
        if image_keys:
            image_keys = image_keys.split(',')
        # redis没有，才全新生成 image_key
        else:
            image_keys = GenFileId(id).get_file_key(self.cmd)
        if image_keys:
            for image_key in image_keys:
                self.send.send(open_id, image_key, 'image')
        else:
            self.send.send(open_id, '可能代币名称（简称）错误，无法匹配到数据；或该币暂不支持', 'text')

    def cmd_process(self, open_id):
        """
        处理用户输入的指令
        """
        if not self.cmd:
            self.send.send(open_id, '指令错误', 'text')
        else:
            self.select_data(open_id)