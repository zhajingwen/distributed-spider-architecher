有个很奇怪的问题点，该任务从palywright中解耦出来就不会出现MySQL连接问题，不知为何
想起来，应该是多线程的问题，一个MySQL的连接不能在多个线程中使用
只能通过启动多个任务来解决并发问题了

需求方并不需要pending接口的数据

### 该任务的启动需要同时启动

```
nohup python manage.py -e prod -s gem.list24h > gemlist24h.log &
nohup python manage.py -e prod -s gem.freemint > gemfreemint.log &
```
