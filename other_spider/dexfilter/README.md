# dexfilter
站点行情定向监控

---
## HAS DONE
- 邮件标准化发送模板
- pandas标准化写入Excel
- 页面分析
- 爬虫开发
- 爬虫测试
- 爬虫落Excel测试
- 爬虫接入代理

## TODO LIST

- 爬虫定时
- 爬虫调SDK发送邮件
- 本地定时调度测试
- 接入目标邮箱，服务器运行

## 问题

- https://github.com/vvanglro/cf-clearance  尝试该项目，rpc调用容器的方式来拿到cf
  - 测试发现该项目好使，能够正常生成cookies cf
  - 之前有一个将所有数据聚合到一个Excel的需求，故存在线程进程等待的问题，比如详情页爬虫
  需要等待确认列表页爬完了，才会进行详情页的采集，就为了不会漏数据都能输出到一张表
  - 但是现在没有这个需求了，需求改成告警了，那么等待也无需存在
  - 当前容器，运行时间长了会无法正常处理job，后面考虑过段时间就做下重启;  有可能是资源耗尽引起的
  - 考虑定期执行这个命令docker restart cf-clearance  如果资源满足的前提下依然会导致服务失效
  - 20221218  8:24发现没有挂，过了一夜仍然健在，怀疑和资源有关系
  - 20221225 有效IP越跑越少，这点很奇怪，得做个监控才行，监控IP可用数量设置一个阈值；或者用程序自动拉取自动补充
  - 
## 依赖容器

```commandline
docker run -d --restart always --network host --name cf-server your-registry.example.com/spider:latest \
--host 0.0.0.0 --port 86 --workers 20

```
