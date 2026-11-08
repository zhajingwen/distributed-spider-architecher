### 需要执行三个命令

- 需要更新该redis key为上个季度最后一个币
```
# string 上个季度上币数据的最后一个币
self.last_coin = 'mainex:lastcoin'
```

- 命令分优先级
```shell
# 获取统计区间内的币清单  依赖playwright
python manage.py -e prod -s coingecko_once.mainexallcoins
# 与coingecko做匹配
python manage.py -e prod -s coingecko_once.mainexmatch
# 将匹配结果导出为csv
python manage.py -e local -s coingecko_once.mainexmatch
# 采集历史交易数据
python manage.py -e local -s coingecko_once.mainextradeinfo
```