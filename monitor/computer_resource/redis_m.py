import time
import logging
from monitor.error_alert import alert
from utils.redisdb import redis_cli


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('REDIS MONITOR')

class RedisM:

    def __init__(self):
        self.key = 'health'
        # self.url = '<LARK_WEBHOOK_ALERT>'
        self.redis_cli = redis_cli()

    def health(self):
        redis_cli().set(self.key,1)

    def getmemroy(self):
        """
        how much memroy used
        """
        info = redis_cli().info()
        used_memory = info['used_memory']
        used_memory_human = info['used_memory_human']
        logger.info(f'used {used_memory_human}')
        # 1024*1024*1024为1G
        # if used memory > 4G alert
        if used_memory > 1024*1024*1024*4:
            msg = f'used memory {used_memory / (1024 * 1024 * 1024)}G'
            alert(msg, self.redis_cli, 'redis')

    def run(self):
        """
        monitor entrance
        """
        while True:
            try:
                # 每分钟轮询一次
                self.health()
                self.getmemroy()
                time.sleep(1*60)
            except:
                msg = 'redis connection error'
                alert(msg, self.redis_cli, 'redis')
