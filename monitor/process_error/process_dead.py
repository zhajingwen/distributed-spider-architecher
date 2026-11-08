import time
import logging
import psutil
from utils.redisdb import redis_cli
from monitor.error_alert import alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Dead Process')


class ProcessDead:

    def __init__(self):
        self.redis_cli = redis_cli()
        self.key_base = 'processes'

    def alive_processes(self):
        ps_alive = []
        # 获取所有进程列表
        for proc in psutil.process_iter():
            try:
                # 获取进程信息
                process_info = proc.as_dict(attrs=['pid', 'cmdline'])
                if 'python' in process_info['cmdline']:
                    name = process_info['cmdline'][-1]
                    if psutil.pid_exists(process_info['pid']):
                        ps_alive.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        ps_alive = list(set(ps_alive))
        return ps_alive

    def run(self):
        """
        入口
        监控现有的，刷新当前目录下所有文件，将新增的纳入监控
        """
        while True:
            processes = self.redis_cli.hgetall(self.key_base)
            alive_processes = self.alive_processes()
            for key in processes:
                value = processes[key]
                value = int(value)
                if value == 1:
                    # 死掉的进程需要报警
                    if key not in alive_processes:
                        msg = f'{key} 该进程已死！！！'
                        alert(msg, self.redis_cli, 'process dead')
            time.sleep(30)
            logger.info('process dead monitoring')


