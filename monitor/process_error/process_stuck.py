import os
import time
import logging
from utils.redisdb import redis_cli
from monitor.error_alert import alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Process Stuck')


class ProcessStuck:

    def __init__(self):
        self.redis_cli = redis_cli()
        self.key_base = 'process_error:{}'
        self.white_list = './premint.log'

    def get_alllog_files(self):
        """
        获取目录下所有的日志文件
        """
        file_list = []
        path = './'
        # 获取当前目录下的所有文件
        for root, dirs, files in os.walk(path):
            for file in files:
                # 使用join函数将文件名称和文件所在根目录连接起来
                file_path = os.path.join(root, file)
                if '.log' in file_path:
                    file_list.append(file_path)
        # 去重
        file_list = list(set(file_list))
        for file in file_list:
            self.judge_status(file)

    def extract_time(self, last_line):
        """
        抽取最后一行的打印日期
        True 表示需要报警
        """
        date_time = last_line.strip().split(' - ')[0].split(',')[0]
        time_tuple = time.strptime(date_time, "%Y-%m-%d %H:%M:%S")
        timestamp = int(time.mktime(time_tuple))
        now = int(time.time())
        time_diff = now - timestamp
        # 超过半小时没有日志打印就告警
        if (time_diff / 60) > 60 * 2:
            return True
        return

    def judge_status(self, path):
        """
        对每个具体的文件进行监控
        """
        alert_status = False
        with open(path, "r") as file:
            lines = file.readlines()
            try:
                num = 0
                while True:
                    num -= 1
                    last_line = lines[num]
                    if last_line.strip():
                        try:
                            alert_status = self.extract_time(last_line)
                            break
                        except:
                            logger.info('此行无日期，往上查询')
                    else:
                        logger.info(f'最后一行为空：{path}')
            # 当num网上推超过了行数，越界了，就会报错
            except:
                logger.warning(f'程序没有正常启动：{path}')
                last_line = '程序没有正常启动'
                alert_status = True
        # 需要报警的
        if alert_status:
            # 过滤不需要报警的
            if path not in self.white_list:
                msg = f'{path}\n该程序夯住了\n{last_line}'
                alert(msg, self.redis_cli, 'process stuck')

    def run(self):
        """
        入口
        监控现有的，刷新当前目录下所有文件，将新增的纳入监控
        """
        while True:
            self.get_alllog_files()
            # 10分钟扫一次
            time.sleep(10*60)
            logger.info('process stuck monitoring')