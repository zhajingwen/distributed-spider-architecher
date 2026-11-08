### 各种监控告警的机器人
- computer_resource: 计算资源监控
- insight_tgbot: telegram bot insight 转发机器人
- twitterkol: twitter kol 提到的热门加密货币监控推送到飞书



- run
```commandline
nohup python manage.py -e prod -s monitor.run > monitor.log &
nohup python manage.py -e prod -s monitor.twitterkol > monitortwitterkol.log &
# 可以通过 -e test 打到测试频道中
nohup python manage.py -e prod -s monitor.insightbot > monitorinsightbot.log &
nohup python manage.py -e prod -s monitor.logerror > monitorlogerror &
```