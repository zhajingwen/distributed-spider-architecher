import os
import ccxt



import redis


def redis_cli():
    redis_conn = redis.StrictRedis(
        host=os.getenv('CMC_TEST_DB_HOST', ''),
        port=6379,
        db=0,
        # username=config.REDIS_USERNAME,
        password=os.getenv('CMC_TEST_DB_PASSWORD', ''),
        decode_responses=True,
        ssl=True
    )
    return redis_conn


key = 'cmc:strong:binance:symbols'
# exchange = ccxt.binance({'proxies': proxies})
exchange = ccxt.binance()
# exchange.load_markets()
# ohlcv = exchange.fetch_ohlcv('ETH/USDT', timeframe='1h', limit=1000)
# print(ohlcv)
x = exchange.load_markets()
# print(x)
with redis_cli().pipeline(transaction=False)as pipe:
    for i in x:
        # print(i)
        symbol = i.split('/')[0].strip()
        print(symbol)
        pipe.sadd(key,symbol)
    pipe.execute()
