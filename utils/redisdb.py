import redis
from config import config
import os

env = os.environ.get('env')

def redis_cli():
    redis_conn = redis.StrictRedis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        username=config.REDIS_USERNAME,
        password=config.REDIS_PASSWORD,
        decode_responses=True,
        ssl=True if env != 'pre' else False #aws用了ssl
    )
    return redis_conn
