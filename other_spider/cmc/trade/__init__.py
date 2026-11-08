import os
from binance.spot import Spot


# Get server timestamp
# print(client.time())
# Get klines of BTCUSDT at 1m interval
# print(client.klines("BTCUSDT", "1m"))
# Get last 10 klines of BNBUSDT at 1h interval
# print(client.klines("BNBUSDT", "1h", limit=10))

# API key/secret are required for user data endpoints
api_key = os.getenv('BINANCE_SPOT_API_KEY', '')
api_secret = os.getenv('BINANCE_SPOT_API_SECRET', '')
# client = Spot(api_key=api_key, api_secret=api_secret)
# client = Client(api_key, api_secret)
Client = Spot(api_key,api_secret)
# 需要注意的是在本地环境，用clash是跑不通的，ISO如果不开全局代理也无法访问binance APP  以前不是这样，感觉是binance改版了
print(Client.account())

# Get account and balance information
# print(client.account())


