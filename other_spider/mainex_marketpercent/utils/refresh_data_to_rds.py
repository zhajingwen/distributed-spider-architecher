import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Refresh RDS')

class RDS:
    def __init__(self):
        self.insert_filter_key = 'mainexmarketpercent:filter:{}'

    def insert_rds(self, redis_cli, insert_sql, rds, id):
        """
        同一日内不会重复刷新数据库
        """
        key = self.insert_filter_key.format(id)
        insert_status = redis_cli.get(key)
        # 更新数据
        if 'update' in insert_sql:
            logger.info(insert_sql)
            rds.insert(insert_sql)
        else:
            if not insert_status:
                rds.insert(insert_sql)
                redis_cli.setex(key, 12*60*60, 1)