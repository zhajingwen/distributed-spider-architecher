import time
import logging
from utils.rds import DataUtils
from monitor.error_alert import alert
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MYSQL MONITOR')

class MysqlM:

    def __init__(self):
        self.redis_cli = redis_cli()

    def howmuchused(self):
        """
        select mysql have used disk
        """
        # connection maybe error
        try:
            con = DataUtils()
            sql = "select truncate(data_length/1024/1024, 2) as 'usedM' from information_schema.tables order by data_length desc, index_length desc;"
            res = con.select(sql)
        except:
            msg = 'mysql connection error'
            alert(msg, self.redis_cli, 'mysql')
            return
        nums = []
        for i in res:
            usedM = i['usedM']
            if usedM:
                nums.append(usedM)
        logger.info(f'used {sum(nums)}M')
        # if mysql used disk more than 4G alert
        if sum(nums) > 1024*4:
            msg = f'mysql used {sum(nums)/1024}G'
            alert(msg, self.redis_cli, 'mysql')

    def run(self):
        """
        monitor entrance
        """
        while True:
            # 每分钟轮询一次
            self.howmuchused()
            time.sleep(1*60)