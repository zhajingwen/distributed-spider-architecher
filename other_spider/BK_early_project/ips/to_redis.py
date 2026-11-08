import logging
import time
from hashlib import md5
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('IP STORE')

class IpStore:

    def __init__(self):
        self.redis_cli = redis_cli()
        self.ip_store_key = 'bk-early:ips:store'

    def redishash(self):
        """
        write ips to redis
        """
        # redis_c=redis_cli()
        with self.redis_cli.pipeline(transaction=False)as pipe:
            with open('other_spider/BK_early_project/ips/proxyurl')as f:
                content = f.read()
                for row in content.strip().split('\n'):
                    ip = row.strip()
                    key_id = md5(ip.encode()).hexdigest()
                    pipe.hset(self.ip_store_key,key_id,ip)
                    logger.info(f'{ip} 入库')
            pipe.execute()
            logger.info(f'全部IP入库完毕')
    def check_ipstore_idle(self):
        """
        check how much ips are left in the redis ipstore
        """
        length = self.redis_cli.hlen(self.ip_store_key)
        logger.info(f'当前IP仓库剩余：{length}')
        if length < 10:
            logger.info('IPs restock')
            self.redishash()
    def ipstore_monitor(self):
        """
        scheduled scan the left num of ips in ipsstore of redis
        """
        while True:
            # scan every 20 s
            self.check_ipstore_idle()
            time.sleep(20)

