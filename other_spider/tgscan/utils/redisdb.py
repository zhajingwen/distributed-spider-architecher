import redis
# from config import config
import os

env = os.environ.get('env')
if env == 'local':
    # host = '127.0.0.1'
    host = os.getenv('TGSCAN_REDIS_HOST', '')

else:
    # host = '<TGSCAN_REDIS_HOST>'
    host = '127.0.0.1'



def redis_cli():
    redis_conn = redis.StrictRedis(
        host=host,
        port=6379,
        # db=config.REDIS_DB,
        # username=config.REDIS_USERNAME,
        password=os.getenv('TGSCAN_REDIS_PASSWORD', ''),
        decode_responses=True,
        # ssl=True if env != 'pre' else False #aws用了ssl
    )
    return redis_conn
