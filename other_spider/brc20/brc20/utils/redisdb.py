import redis
from config import config


def redis_cli():
    redis_conn = redis.StrictRedis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        username=config.REDIS_USERNAME,
        password=config.REDIS_PASSWORD,
        decode_responses=True
    )
    return redis_conn
