import time

content = '2023-03-16 15:15:37,587 - TG BOT - INFO - 循环监控：273'
date_time = content.strip().split(' - ')[0].split(',')[0]
# date_str = "2022-06-01 12:00:00"
time_tuple = time.strptime(date_time, "%Y-%m-%d %H:%M:%S")
timestamp = int(time.mktime(time_tuple))

print(timestamp)

