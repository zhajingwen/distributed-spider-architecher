import psutil
import logging
import time
from monitor.error_alert import alert
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Threads Number Monitor')

class Processes:
    def __init__(self):
        self.redis_cli = redis_cli()

    def theads_overflow(self):
        """
        获取服务器所有线程数
        线程数阈值为50w，如果超过，返回True
        """
        total_threads = psutil.cpu_count(logical=True)  # 获取CPU逻辑核心数
        for proc in psutil.process_iter():
            try:
                pinfo = proc.as_dict(attrs=['pid', 'num_threads'])
            except psutil.NoSuchProcess:
                pass
            else:
                total_threads += pinfo['num_threads']
        logger.info(f'线程数: {total_threads}')
        # 超过50w报警
        if total_threads > 500000:
            return True
        else:
            return False

    def max_threads_come(self):
        """
        查询排名靠前的 创建线程数比较多的进程
        组织成文本并且返回
        """
        processes = {}
        for proc in psutil.process_iter():
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
            except psutil.NoSuchProcess:
                pass
            else:
                if 'python' in pinfo['cmdline']:
                    name = pinfo['cmdline'][-1]
                else:
                    name = pinfo['cmdline']
                processes[pinfo['pid']] = {'name': name, 'threads': proc.num_threads()}
        # 按线程数排序
        sorted_processes = sorted(processes.items(), key=lambda x: x[1]['threads'], reverse=True)
        alert_msg = ''
        # 打印前10个进程
        for pid, info in sorted_processes[:10]:
            logger.info(f"Process {info['name']} (PID {pid}) created {info['threads']} threads \n")
            alert_msg += alert_msg
        return alert_msg

    def run(self):
        """
        10s扫一次
        循环监控
        """
        while True:
            status = self.theads_overflow()
            if status:
                content = self.max_threads_come()
                alert(content, self.redis_cli, 'Threads Overflow')
            time.sleep(10)
            logger.info('running')