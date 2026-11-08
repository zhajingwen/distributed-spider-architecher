import os
import logging
from utils.rds import DataUtils
from other_spider.birdeye.seek_information.gen_csv_and_upload import GenFileId
from utils.lark_bot_response import Send

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Process CMD')

class LoadData:
    def __init__(self):
        self.rds = DataUtils()
        self.file_key = GenFileId()
        app_id = os.getenv('LARK_APP_ID_BIRDEYE', '')
        app_secret = os.getenv('LARK_APP_SECRET_BIRDEYE', '')
        self.send = Send(app_id, app_secret, 'birdeyegems')

    def cmd_format(self, message):
        """
        对指令进行格式化处理
        """
        if '/find' in message:
            cmd = message.strip().replace('/find', '')
            try:
                cmd = int(cmd)
                return cmd
            except:
                logger.info(f'指令错误：{message}')
                return
        else:
            logger.info(f'指令错误：{message}')
            return

    def select_data(self, hours, open_id):
        """
        根据指令从数据库加载数据 + 将数据转换为csv文件发送给用户
        """
        file_key = self.file_key.get_file_key(hours, open_id)
        if file_key:
            self.send.send(open_id, file_key, 'file')

    def cmd_process(self, message, open_id):
        """
        处理用户输入的指令
        """
        cmd = self.cmd_format(message)
        if not cmd:
            self.send.send(open_id, '指令错误', 'text')
            # return '指令错误'
        else:
            self.select_data(cmd, open_id)