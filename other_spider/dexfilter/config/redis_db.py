import os
import redis

def redis_cli_aliyun():
    REDIS_HOST = os.getenv('DEXFILTER_REDIS_HOST', '')
    REDIS_PASSWORD = os.getenv('DEXFILTER_REDIS_PASSWORD', '')
    redis_conn = redis.StrictRedis(
        host=REDIS_HOST,
        port=6379,
        db=0,
        password=REDIS_PASSWORD,
        username='redis_rw',
        decode_responses=True
    )
    return redis_conn
