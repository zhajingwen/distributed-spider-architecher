### spider 层面的个性化设置

---
- `chang_ua`：支持通过spider类属性，来自定义是否切换**UA**；属性非强制定义（可省略，省略则默认开启）
  > 比如：chang_ua = False  #表示不走UA middleware自动切换UA

- `proxy`：支持通过spider类属性，来自定义是否走**代理**；属性非强制定义（可省略，省略则默认开启）
  > 比如： proxy = False #表示不走代理middleware自动切换代理

- `cron_job`：支持通过spider类属性，来自定义是否用crontab语法来执行**定时爬虫**；属性非强制定义（可省略，省略则不开启）
  > 比如：cron_job = "1 0 * * *"  #表示每日0点1分启动

- `schedule_time`：支持通过spider类属性，来自定义**定时爬虫**（间隔多久爬一次）；不设置该变量则表示不启用
  > 比如：schedule_time = 12 * 30  #表示每30分钟调度一次
