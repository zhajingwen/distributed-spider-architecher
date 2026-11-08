from other_spider.tgscan.utils.redisdb import redis_cli as target_redis
from utils.redisdb import redis_cli as from_redis


class Transfer:
    def __init__(self):
        # 迁移的目标地址
        self.redis_cli_target = target_redis()
        # 迁移数据源
        self.redis_cli_from = from_redis()

    def move_str(self):
        """
        迁移字符串类型的数据
        """
        key1 = 'tgscan:exchange_fee_demo_key:your_test_bot'
        key2 = 'tgscan:exchange_fee_demo_key:your_bot'
        key3 = 'tgscan:username_demo:your_test_bot'
        key4 = 'tgscan:username_demo:your_bot'
        keys = [key1,key2,key3,key4]
        for key in keys:
            value = self.redis_cli_from.get(key)
            self.redis_cli_target.set(key,value)
        print('所有字符串类型的数据迁移成功')

    def move_set(self):
        """
        迁移钱包地址
        """
        key = 'tgscan:wallets'
        members = self.redis_cli_from.smembers(key)
        with self.redis_cli_target.pipeline(transaction=False) as pipe:
            for m in members:
                pipe.sadd(key, m)
            pipe.execute()
        print('钱包地址迁移成功')

    def move_hash(self):
        """
        迁移用户余额信息
        """
        key = 'tgscan:users:balance'
        data = self.redis_cli_from.hgetall(key)
        with self.redis_cli_target.pipeline(transaction=False)as pipe:
            for name in data:
                value = data[name]
                pipe.hset(key, name, value)
            pipe.execute()
            print('用户余额迁移成功')

    def imigrate(self):
        # self.move_str()
        # self.move_set()
        self.move_hash()
