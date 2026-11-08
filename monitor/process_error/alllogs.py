import os
import time
import queue
import logging
from threading import Thread
from utils.redisdb import redis_cli
from traceback import format_exc
from monitor.error_alert import alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Log Error')


class Watch:
    def __init__(self):
        # 所有log文件
        self.files = []
        # 已经在监控中的log文件
        self.watching_files = []
        self.queue = queue.Queue()
        self.redis_cli = redis_cli()
        self.key_base = 'process_error:{}'
        self.web_hook_api = os.getenv('LARK_WEBHOOK_ALERT', '')
        self.not_alert_paths = ['./mxplay.log']


    def get_alllog_files(self):
        """
        获取目录下所有的日志文件
        """
        while True:
            path = './'
            # 获取当前目录下的所有文件
            for root, dirs, files in os.walk(path):
                for file in files:
                    # 使用join函数将文件名称和文件所在根目录连接起来
                    file_path = os.path.join(root, file)
                    if '.log' in file_path:
                        # print(file_path)
                        self.files.append(file_path)
            # 去重
            files = set(self.files)
            self.files = list(files)
            # 将未被监控的日志文件加入队列
            for file in files:
                if file not in self.watching_files:
                    self.watching_files.append(file)
                    self.queue.put(file)
            # 每小时扫一次
            time.sleep(60*60)

    def white_list(self):
        """
        含有以下内容不告警
        """
        not_filter_content = [
            'cxt_get网络请求失败，重试..',
            'req网络请求失败，重试',
            'Proxy Error',
            '重试超过次数',
            'get_gas网络请求失败',
            'response code error',
            '代理失败，无cookies',
            'werkzeug',
            'ProxyError',
            'MaxRetryError',
            'SSL',
            'ConnectionError',
            'DEBUG'
        ]
        return not_filter_content


    def alert_status(self,line,path):
        """
        是否需要告警
        """
        status = True
        not_alert_content_list = self.white_list()
        # 只要有一个元素存在于line中那么就不告警
        for not_a_c in not_alert_content_list:
            if not_a_c in line:
                status = False
        # 如果存在于不需要告警的白名单目录，就返回False
        if path in self.not_alert_paths:
            status = False
        return status

    def filter(self, path):
        """
        对每个具体的文件进行监控
        """
        file = open(path)
        num = 0
        read_success = False
        while True:
            key = self.key_base.format(path)
            if num == 0:
                value = self.redis_cli.get(key)
                if value:
                    value = int(value)
                    try:
                        file_length = len(file.read())
                    except:
                        logger.warning(f'{path} 无法正常读取日志')
                        return
                    # 文件重置过
                    if file_length+2 < value:
                        logger.info(f'文件已被重置 {path}')
                    else:
                        file.seek(value)
                        logger.info(f'初始化游标值：{path} {value}')
            where = file.tell()
            num += 1
            # 每1000行刷新一次redis缓存
            if num %1000 == 0:
                self.redis_cli.set(key,where)
            try:
                line = file.readline()
                # 防止日志过度打印，只打印一次
                if not read_success:
                    read_success = True
                    logger.info(f'文件读取成功：{path}')
            except:
                logger.error(format_exc())
                logger.error(f'{path} 该文件无法被readline,初始化从头开始读')
                file.seek(0)
                continue
            if not line:
                time.sleep(1)
                file.seek(where)
            else:
                new_line = line.lower()
                if 'error' in new_line:
                    # 过滤文本和路径
                    status = self.alert_status(line, path)
                    # 为True 则告警
                    if status:
                        content = f'{line}\n----{path}----'
                        alert(content, self.redis_cli, 'logserror')

    def run(self):
        """
        入口
        监控现有的，刷新当前目录下所有文件，将新增的纳入监控
        """
        # 刷新log文件列表，并且将新的log文件加入任务队列
        get_file_t = Thread(target=self.get_alllog_files)
        get_file_t.start()
        while True:
            file = self.queue.get()
            if file:
                t = Thread(target=self.filter, args=(file,))
                t.start()
            time.sleep(1)