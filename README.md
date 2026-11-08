***目录结构***

---

|目录                      |说明                                   |
|-------------------------|---------------------------------------|
|other_spider             |非scrapy爬虫         |
|scrapy_spider            |所有scrapy分布式爬虫                    |
|test　　　　             |测试类脚本                               |
|utils　　　　　          |工具类脚本                               |
|requirements_backup.txt |基础镜像依赖的Python库                    |
|requirements.txt        |新增依赖的Python库                    |

***配置***

---
所有密码、Token、Webhook、代理账号等敏感信息都通过**环境变量**读取，仓库里没有任何真实凭证。

```bash
cp .env.example .env      # 按需填写，.env 已被 .gitignore 忽略
set -a && source .env && set +a
```

- 公共配置（Redis / MySQL / 代理 / 阿里云 SLS）在 `config/base.py` 中，从环境变量读取，`-e` 参数选择的环境类（local/test/pre/prod）都继承自它
- 各爬虫、机器人用到的 Lark Webhook、Telegram Bot Token、第三方 API Key 等变量在 `.env.example` 中按类别列出，并注明使用它的模块；只需要填写你要运行的模块用到的变量
- 文档和注释中的 `<VAR_NAME>` 是占位符，对应同名环境变量
- k8s / Dockerfile / CI 配置中的镜像仓库地址为 `your-registry.example.com`，域名为 `example.com`，请替换为你自己的

***启动命令***

---
 - 根据情况选择python
 - `python manage.py -e test -t no -d 20200719 -s scrapy.tencent_benghuai3_buluo`

***参数说明***

---
* -e`必须参数` 是环境的意思，可以传入 local,prod,test或者不传，不传入默认是线上环境
* -s`必须参数` 表示启动的对应的爬虫类型（scrapy或者其他爬虫）和爬虫名,中间用.分割
* -t`非必须参数` 表示是否传入历史队列，yes or no 
* -d`非必须参数` 指定日期，如果不指定，可以不传参或者传now

***scrapy爬虫自定义类属性***

--- 
```
    name = 'bilibili_bh3_search_videodetail'
    redis_key = f"{name}:start_url"
    change_ua = True
    start_urls = ['http://api.ipify.org/']
    topic = 'popinion-data-crawl-bilibili'
    # 时间间隔调度：调度周期1天
    schedule_time = 12 * 60 * 24
    # 固定时间调度：cronjob语法 14点1分启动
    cron_job = "1 14 * * *"
    redis_c = redis_cli()
    history_type = False
    proxy = 'china'
```

***三个环境***

---
 - dev:开发环境
 - test:测试环境（已经搭建测试docker集群）
 - prod:生产环境
 - pre 预发布，部分迁移的一个环境，迁移到香港了
 
***代理情况***

---
to do

***基础镜像***

---
- 不带selenium的基础镜像

`your-registry.example.com/spider:latest`

- 带有google指数环境的镜像

`your-registry.example.com/spider:latest`


***所有爬虫***

---
启动命令

```commandline
nohup python manage.py -e prod -s premint.webapi > premint.log &
nohup python manage.py -e prod -s gem.detail > gemdetail.log &
nohup python manage.py -e prod -s gem.freemint > gemfreemint.log &
nohup python manage.py -e prod -s cmc.m > cmcm.log &
nohup python manage.py -e prod -s cmc.tg > cmctg.log &
nohup python manage.py -e prod -s cmc.m14 > cmcm14.log &
nohup python manage.py -e prod -s cmc.backtest > cmcbacktest.log &
nohup python manage.py -e prod -s twitterscan.run > twitterscan.log &
nohup python manage.py -e prod -s googletrends.t > googletrends.log &
nohup python manage.py -e prod -s dexfilter.list > dexfilterlist.log &
nohup python manage.py -e prod -s dexfilter.detail > dexfilterdetail.log &
nohup python manage.py -e prod -s dexfilter.gen > dexfiltergen.log &
nohup python manage.py -e prod -s dexfilter.ips > dexfilterips.log &
nohup python manage.py -e prod -s dexfilter.user_a1 > dexfilteruser_a1.log &
nohup python manage.py -e prod -s dexfilter.user_a2 > dexfilteruser_a2.log &
nohup python manage.py -e prod -s dexfilter.user_a3 > dexfilteruser_a3.log &
nohup python manage.py -e prod -s cmc_history.spider > cmchistoryspider.log &
nohup python manage.py -e prod -s nswap.list > nswaplist.log &
nohup python manage.py -e prod -s nswap.raffles > nswapraffles.log &
nohup python manage.py -e prod -s nswap.detail > nswapdetail.log &
nohup python manage.py -e prod -s monitor.run > monitor.log &
nohup python manage.py -e prod -s monitor.twitterkol > monitortwitterkol.log &
nohup python manage.py -e prod -s monitor.insightbot > monitorinsightbot.log &


nohup python manage.py -e prod -s mainex.ccxt > mxccxt.log &
nohup python manage.py -e prod -s monitor.process_error > process_error &
nohup python manage.py -e prod -s coingecko_once.run > coingecko_once.log &
nohup python manage.py -e prod -s ethbtc_volume.run > ethbtc_volume.log &
nohup python manage.py -e prod -s kol_insight.run > kol_insight.log &
nohup python manage.py -e prod -s BK_early_project.run > BK_early_project.log &
nohup python manage.py -e prod -s mongrel_dog.list > mongrel_doglist.log &
nohup python manage.py -e prod -s mongrel_dog.detail > mongrel_dogdetail.log &
nohup python manage.py -e prod -s mongrel_dog.deldata > mongrel_dogdeldata.log &
nohup python manage.py -e prod -s cmc.strong > cmcstrong.log &
nohup python manage.py -e prod -s brc20.brc-20 > brc20brc-20.log &
nohup python manage.py -e prod -s brc20.gencookies > brc20gencookies.log &
nohup python manage.py -e prod -s brc20.ipmonitor > brc20ipmonitor.log &
nohup python manage.py -e prod -s brc20.unisat > brc20unisat.log &
nohup python manage.py -e test -s bestinslot.run > bestinslot.log &
```

```commandline
# 下面两个应该中止了，由于nansen的原因
nohup python manage.py -e prod -s crypto_scan.eth > crypto_scaneth.log &
nohup python manage.py -e prod -s crypto_scan.tt > crypto_scantt.log &
```


***目前服务器已经开放的端口***

 - 443 nginx         外网
 - 86 Docker CF绕过   内网

---
***K8s内使用的端口***   第一版（**废弃**）
- 30001 (8443>443>30001) k8s dashboard
- 30002 (5601>5601>30002) kibana
- 30003 (84>84>30003) bk早期项目机器人
- 30004 (83>83>30004) TG机器人（转发热点）
- 30005 (87>87>30005) dappradar restful api    放弃
- 30006 (88>88>30005)lark机器人similarweb查网站流量
- 6443  k8s restful api 端口
---
***K8s内使用的端口***   第二版
> 通过 k8s内的DNS地址解析到目标APP
- 集群内暴露的端口 （容器内应用端口 > 集群内暴露的端口）
- 443 (8443>443) k8s dashboard
- 5601 (5601>5601) kibana
- 84 (84>84) bk早期项目机器人
- 83 (83>83) TG机器人（转发热点）
- 87 (87>87) dappradar restful api    放弃
- 88 (88>88)lark机器人similarweb查网站流量
- 6443  k8s restful api 端口
- 90 (90>90)项目评审机器人回调地址：https://example.com/project-review
- 89 (89>89)BK筛项目草稿 机器人回调地址：https://example.com/bkproject-document
- 91 (91>91)BK筛项目草稿 机器人回调地址：https://example.com/wallet-balance
- 2375 > 2375   Docker in Docker
- 2376 > 2376   Docker in Docker2
- 8080 > 8080   Jenkins
- 50000 > 50000 Jenkins
- 5000 > 5000   Docker registry
- 5432 > 5432   gitea 依赖的数据库端口
- 3000 > 3000   gitea web端口
- 96 > 22       gitea SSH连接，用于代码pull和push


---
### 宿主机运行程序
```commandline
nohup python manage.py -e prod -s cmc.m > cmcm.log &
nohup python manage.py -e prod -s cmc.tg > cmctg.log &
nohup python manage.py -e prod -s cmc.m14 > cmcm14.log &
nohup python manage.py -e prod -s cmc.strong > cmcstrong.log &
nohup python manage.py -e prod -s twitterscan.run > twitterscan.log &
nohup python manage.py -e prod -s googletrends.t > googletrends.log &
nohup python manage.py -e prod -s nswap.list > nswaplist.log &
nohup python manage.py -e prod -s nswap.raffles > nswapraffles.log &
nohup python manage.py -e prod -s nswap.detail > nswapdetail.log &
# 需要再宿主机也起一份进程
nohup python manage.py -e prod -s monitor.hardware > monitorhardware.log &
nohup python manage.py -e prod -s monitor.process_error > process_error &
nohup python manage.py -e prod -s mainex.ccxt > mxccxt.log &
nohup python manage.py -e prod -s mainex.coinlist > mxcoinlist.log &
nohup python manage.py -e prod -s ethbtc_volume.run > ethbtc_volume.log &
nohup python manage.py -e prod -s kol_insight.run > kol_insight.log &
nohup python manage.py -e prod -s mongrel_dog.list > mongrel_doglist.log &
nohup python manage.py -e prod -s mongrel_dog.detail > mongrel_dogdetail.log &
nohup python manage.py -e prod -s mongrel_dog.deldata > mongrel_dogdeldata.log &
# 倒闭了
nohup python manage.py -e prod -s brc20.brc-20 > brc20brc-20.log &
# 倒闭了
nohup python manage.py -e prod -s brc20.gencookies > brc20gencookies.log &
# 倒闭了
nohup python manage.py -e prod -s brc20.ipmonitor > brc20ipmonitor.log &
# 倒闭了
nohup python manage.py -e prod -s brc20.addfields > brc20addfields.log &
# 倒闭了
nohup python manage.py -e prod -s brc20.unisat > brc20unisat.log &

nohup python manage.py -e prod -s bestinslot.run > bestinslot.log &
nohup python manage.py -e prod -s opensea.list > opensealist.log &
nohup python manage.py -e prod -s opensea.pending > openseapending.log &
nohup python manage.py -e prod -s opensea.detail > openseadetail.log &
nohup python manage.py -e prod -s mintfun.list > mintfunlist.log &
nohup python manage.py -e prod -s mintfun.detail > mintfundetail.log &
nohup python manage.py -e prod -s scrapy.crypto_hot_category > scrapycrypto_hot_category.log &

nohup python manage.py -e prod -s scrapy.dappradar > scrapydappradar.log &
nohup python manage.py -e prod -s scrapy.galxe > scrapygalxe.log &
nohup python manage.py -e prod -s scrapy.lineascan > scrapylineascan.log &
nohup python manage.py -e prod -s BK_early_project.ipmonitor > BK_early_projectipmonitor.log &
nohup python manage.py -e prod -s BK_early_project.gencookies > BK_early_projectgencookies.log &
nohup python manage.py -e prod -s dappradar_daily.run > dappradar_daily.log &


similarweb

# 需要暴露容器端口的进程
nohup python manage.py -e prod -s monitor.tginsightbot > monitortginsightbot.log &
nohup python manage.py -e prod -s BK_early_project.run > BK_early_project.log &
nohup python manage.py -e prod -s similarweb.run > similarweb.log &
```

---

- `google trends relationwords` 和 `stweet` 这两个项目的第三方依赖代码都要做修改（自定义）

- 需要注意的是由于流水线配置的限制，目前自动化部署只能够部署该资源
  - 名称：spiders，
  - 类型：deployment
  - namespaces：default
> 具体的部署脚本如下（集成在 CI/CD 流水线中）
```shell
cd $EXE_PATH
sed -i "s/spider:[^[:space:]]*/spider:$DOCKER_IMAGE_TAG/" k8s.yml
apt update
apt install curl -y
curl -H "Authorization: Bearer <K8S_API_TOKEN>" \
     -H "Content-Type: application/yaml" \
     -X PUT \
     --data-binary "@k8s.yml" \
     https://example.com/k8sapi/apis/apps/v1/namespaces/default/deployments/spiders
```


- k8s.yml 不依赖playwright 结合基础镜像使用：your-registry.example.com/spider:latest
- playwright.yml 依赖playwright 结合基础使用：your-registry.example.com/spider:latest
- setuptools==60.9.0 该版本存在问题，导致无法安装web3

### 每日定时告警

---

```shell
# 每日mainex上线的币 高涨幅的告警
python manage.py -e test -s mainex.alert 
# 每日googletrends数据采集
python manage.py -e test -s googletrends_api.oldapi
# Jack每日热门板块告警（Jack）
python manage.py -e test -s hot_category.run
# BTC gas费每日推送
python manage.py -e test -s btc_gas.run
# BTC 基于高汇率币的所属板块逆推板块计数， 对币所属板块计数后对累计值排序推送；依赖于scrapy.scan_high_exchange_rate
python manage.py -e test -s scrapy.crypto_hot_category
python manage.py -e test -s scrapy.scan_high_exchange_rate
# dappradar 数据采集
python manage.py -e test -s dappradar_daily.run
# 刷新Mainex listing all coins marketshare info to rds 8 am everyday
python manage.py -e test -s mainex_marketpercent_bot.refresh
# marketshare 告警
python manage.py -e test -s mainex_marketpercent.refresh
# trendx 落库
python manage.py -e test -s twitterscan.insert
```