import ccxt

import ccxt

# 初始化交易所
binance_exchange = ccxt.binance({
    'timeout': 15000,
    'enableRateLimit': True
})
symbol = 'BTC/USDT'
# K线数据数据获取
x = binance_exchange.fetch_ohlcv(symbol,limit=10)
print(x)



def get_k_price(exchange_id, symbol):
    """
    <BINANCE_API_KEY_CCXT>
<BINANCE_API_SECRET_CCXT>
{"apiKey":"<BINANCE_API_KEY_CCXT>","secretKey":"<BINANCE_API_SECRET_CCXT>","comment":"ccxt量化"}

    """
    # instantiate the exchange by id
    exchange = getattr(ccxt, exchange_id)()
    # 将时间转换成毫秒的时间戳
    # if isinstance(since, str):
    #     since = exchange.parse8601(since)
    exchange.load_markets()
    # print(symbol, timeframe, since, limit)
    ohlcv = exchange.fetch_ohlcv(symbol, 10)
    # print(ohlcv)
#
# if __name__ == '__main__':
#     get_k_price('binance', 'BTC/USDT')
