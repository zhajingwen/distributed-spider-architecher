import psutil
import logging
import time
from monitor.error_alert import alert
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ECS MONITOR')

class Ecs:

    def __init__(self):
        # self.url = '<LARK_WEBHOOK_ALERT>'
        self.contianer = []
        self.redis_cli = redis_cli()

    def get_ecs_info(self):
        """
        get the ecs computer resource info
        """
        cpuinfo = psutil.cpu_percent(1)
        svmem = psutil.virtual_memory()
        meminfo = svmem[2]
        disk_root = psutil.disk_usage('/')[-1]
        disk_data = psutil.disk_usage('/data')[-1]
        msg = f"""
        cpu used: {cpuinfo}%
        memory used: {meminfo}%
        disk root used: {disk_root}%
        disk data used: {disk_data}%
        """
        logger.info(msg)
        # cpu 内存 磁盘 有任何一个大于80%就告警
        # memory 改为占用50%就告警
        if (cpuinfo > 80 or meminfo > 50 or disk_root > 80 or disk_data > 80):
            self.contianer.append(int(time.time()))
            # 确保容器内始终是定长10个元素
            if len(self.contianer)>10:
                self.contianer = self.contianer[(len(self.contianer)-10):]
            # 容器内没有累积到9个及以上的报警次数，不做后续处理
            if len(self.contianer) < 9:
                return
            time_list = sorted(self.contianer, reverse=True)
            # 如果10分钟内，出现了8次以上的报警，那么就认为是高频报警
            # 只要确定第8个元素的时间戳在10分钟之内，那么就认为有问题
            the_early_time = time_list[7]
            if the_early_time > int(time.time()) - 10*60:
                alert(msg, self.redis_cli, 'hard ware')
                # 重置容器，降低信息频率，确保十分钟内只报1次警
                self.contianer = []
        else:
            logger.info('healthy')

    def run(self):
        """
        monitor entrance
        """
        while True:
            # 每分钟轮询一次
            self.get_ecs_info()
            time.sleep(1*60)
            logger.info('监控中...')