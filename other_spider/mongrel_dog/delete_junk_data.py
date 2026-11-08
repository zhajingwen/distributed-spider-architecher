import time
import logging
from utils.redisdb import redis_cli
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Delete Junk Data')

class DeleteData:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.rds = DataUtils(db='spider')
        self.mysql_table = 'dexscreener2'
        # 从数据删除数据任务
        self.deletedata_jobs = 'mongrel:deletedata:jobs_backup'
        # hash结构，记录代币历史刷新时间戳
        self.coin_price_refresh_time = 'mongrel:coinprice:refreshtime'

    def consumer(self):
        """
        从redis拿任务
        """
        name = self.redis_cli.spop(self.deletedata_jobs)
        if not name:
            logger.info('暂无任务...')
            time.sleep(10)
            return
        self.delete_data(name)

    def delete_data(self, name):
        """
        从mysql删除指定name的数据
        """
        sql = f'delete from {self.mysql_table} where name="{name}";'
        status = self.rds.delete(sql)
        # 执行成功后从价格刷新记录缓存hash结构中剔除该name
        if status:
            self.redis_cli.hdel(self.coin_price_refresh_time,name)

    def run(self):
        """
        入口
        """
        while True:
            self.consumer()



