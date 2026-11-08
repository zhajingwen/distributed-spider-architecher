- coingecko全部币的信息 https://www.coingecko.com/en/api/documentation
> 在页面中 Try /coins/list 接口
- 获取历史数据的接口  https://www.coingecko.com/en/api/documentation
- 在上面的接口清单中均能找到对应的api
- 最好用coingecko的symbol去匹配
- 每个季度跑一次
- spider_tradeinfo_from_redis.py 表示从redis  f'coingecko_once:{market}:symbols'  拿任务
