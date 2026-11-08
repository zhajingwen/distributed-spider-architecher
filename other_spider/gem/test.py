import datetime

timestamp = 1619126400
date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
print(date)
# 2021-04-05 00:00:00


print(type(date))