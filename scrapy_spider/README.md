***启动命令***

---
 - `python manage.py -e test -t no -d 20200719 -s scrapy.tencent_benghuai3_buluo`

***参数说明***

---
* -e`必须参数` 是环境的意思，可以传入 local,prod,test或者不传，不传入默认是线上环境
* -s`必须参数` 表示启动的对应的爬虫类型（scrapy或者其他爬虫）和爬虫名,中间用.分割
* -t`非必须参数` 表示是否传入历史队列，yes or no 
* -d`非必须参数` 指定日期，如果不指定，可以不传参或者传now

***scrapy爬虫全部类属性***

--- 
```
    name = 'bilibili_bh3_search_videodetail'
    redis_key = f"{name}:start_url"
    change_ua = True
    start_urls = ['http://api.ipify.org/']
    # kafka topic
    topic = 'popinion-data-crawl-bilibili'
    # 时间间隔调度：调度周期1天
    schedule_time = 12 * 60 * 24
    # 固定时间调度：cronjob语法 14点1分启动
    cron_job = "1 14 * * *"
    redis_c = redis_cli()
    history_type = False
    # 代理类型，支持走不同的代理，中国或是海外
    proxy = 'china'
```

***scrapy爬虫个性化类属性***

--- 
- 参考`spiders`目录下 README.md


***三个环境***

---
 - dev:开发环境
 - test:测试环境（已经搭建测试docker集群）
 - prod:生产环境
 - pre 预发布，部分迁移的一个环境，迁移到香港了
 
***代理情况***

---
- luminati 海外代理，IP包月200G流量，数据中心的质量

***基础镜像***

---
- 不带selenium的基础镜像

`your-registry.example.com/cryptospider:latest`

- 带有google指数环境的镜像

`your-registry.example.com/spiderpy:googletrends`



***目录结构***

---

| 目录                   | 说明                           |
|----------------------|------------------------------|
| downloadhandlers     | 暂未启用                         |
| ext_pipelines        | 自定义的各种管道（数据输出方式）             |
| extensions　　         | 扩展，包括：定时启动扩展                 |
| items　　　　　           | 所有爬虫的Item类                   |
| middlewares          | 下载中间件：UA、Proxy、Retry         |
| spiders              | 所有爬虫的spider文件                |
| run.py               | 爬虫debug启动入口                  |
| settings.py          | 所有爬虫的全局配置                    |
