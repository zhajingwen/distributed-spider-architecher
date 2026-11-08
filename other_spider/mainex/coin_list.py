from config.exchange import ccxt_exchange
import logging
import time

import ccxt
import json
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mainex Coinlist')

class RefreshCoinlist:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.redis_marketpairs_key = 'mainex:marketpairs'

    def refresh(self):
        """
        获取交易所全部币对信息
        """
        while True:
            try:
                mainex_exchange = ccxt_exchange({
                    'timeout': 15000,
                })
                data = mainex_exchange.load_markets()
                if data:
                    break
                else:
                    logger.error('mainex交易所数据刷新失败，重试...')
                    time.sleep(10)
            except:
                logger.error('mainex交易所数据刷新失败，重试...')
                time.sleep(10)
        return data

    def get_data(self):
        """
        拿到交易所币对清单并且写入redis
        """
        data  = self.refresh()
        with self.redis_cli.pipeline(transaction=False) as pipe:
            for marketpair in data:
                if ':' in marketpair:
                    continue
                if 'USDT' not in marketpair:
                    continue
                pipe.hset(self.redis_marketpairs_key, marketpair, 1)
            pipe.execute()
        marketpairs_length = self.redis_cli.hlen(self.redis_marketpairs_key)
        logger.info(f'交易所全量币对刷新成功，交易对总量：{marketpairs_length}')

    def run(self):
        """
        10分钟刷新一次
        """
        logger.info('开始刷新币对列表任务（10m一次）')
        while True:
            self.get_data()
            time.sleep(10*60)