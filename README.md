# cryptospider

面向加密货币市场的数据采集与告警平台。这个仓库包含几十个采集任务、Lark/Telegram 机器人和监控程序，统一由 `manage.py` 启动，打成同一个 Docker 镜像，以多容器 Deployment 的形式运行在 Kubernetes 上。

采集的数据源包括 CoinMarketCap、CoinGecko、DexScreener、OpenSea、Galxe、DappRadar、Google Trends、Twitter 和链上浏览器等。数据写入 MySQL / Redis，结果通过 Lark（飞书）、Telegram 和邮件推送。

---

## 目录

- [架构概览](#架构概览)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [命令行入口](#命令行入口)
- [两类任务](#两类任务)
- [配置与环境](#配置与环境)
- [部署](#部署)
- [对外服务与端口](#对外服务与端口)
- [任务清单](#任务清单)
- [监控](#监控)
- [注意事项](#注意事项)

---

## 架构概览

系统从上到下分为交付部署、集群运行、反爬基础设施、存储、推送交互几层，任务从统一入口按 `project` 分发到 Scrapy 爬虫、独立任务、监控三类执行单元。

```mermaid
flowchart TB
    %% ========== 外部数据源 ==========
    subgraph SRC["🌐 外部数据源"]
        direction LR
        S1["行情聚合<br/>CoinMarketCap · CoinGecko"]
        S2["DEX / 链上<br/>DexScreener · Birdeye · Lineascan · DeBank"]
        S3["NFT / 铭文<br/>OpenSea · mint.fun · BestInSlot"]
        S4["Web3 平台<br/>Galxe · DappRadar · Whales Market"]
        S5["社媒 / 舆情<br/>Twitter · Telegram · Google Trends"]
        S6["交易所<br/>CCXT · 交易所公告"]
    end

    %% ========== 交付与部署 ==========
    subgraph DEPLOY["🚀 交付与部署"]
        direction LR
        GIT["Git 仓库<br/>master"] --> CI["CI/CD 流水线<br/>.devops/"]
        CI -->|"docker build<br/>tag = commit id"| REG["镜像仓库<br/>spider:commit-id"]
        CI -->|"PUT k8s.yml"| K8SAPI["k8s API"]
    end

    %% ========== Kubernetes 集群 ==========
    subgraph K8S["☸️ Kubernetes 集群（同一镜像 · 每个任务一个容器）"]
        direction TB

        subgraph WORKLOADS["工作负载"]
            direction LR
            W1["Deployment<br/>spiders<br/>常驻任务"]
            W2["Deployment<br/>playwright<br/>浏览器任务"]
            W3["Deployment<br/>tgscan<br/>TG 消息监听"]
            W4["Job<br/>spiders-once<br/>一次性任务"]
        end

        subgraph ENTRY["统一入口"]
            direction LR
            MANAGE["manage.py<br/>-e env · -s project.name<br/>-t history · -d date"]
            CFG["config/<br/>BaseConfig ← 环境变量<br/>Local · Test · Pre · Prod"]
            DISPATCH{"commands/run_spider<br/>按 project 分发"}
            MANAGE --> CFG --> DISPATCH
        end

        subgraph SCRAPY["🕷️ scrapy_spider · 分布式爬虫"]
            direction TB
            EXT["调度扩展<br/>cron_job · schedule_time<br/>空闲时重投种子"]
            SCH["scrapy-redis<br/>Scheduler · DupeFilter<br/>断点续爬"]
            SPD["Spiders<br/>galxe · dappradar · debank<br/>lineascan · hot_crypto_category"]
            MW["下载中间件<br/>随机 UA → 代理注入<br/>→ 失败换代理重试"]
            PL["Item Pipelines<br/>MySQL · MongoDB<br/>Kafka · SLS"]
            EXT --> SCH --> SPD --> MW
            SPD --> PL
        end

        subgraph OTHER["⚙️ other_spider · 独立任务 run(name)"]
            direction TB
            POLL["轮询采集 / 策略告警<br/>cmc · mainex · mongrel_dog<br/>opensea · twitterscan · hot_category"]
            BOT["Flask 机器人服务<br/>:83 – :95<br/>项目评审 · 钱包余额 · 市占率 …"]
            ANTI["反爬辅助<br/>ipmonitor 代理 IP 池<br/>gencookies cf_clearance"]
        end

        subgraph MON["🩺 monitor · 监控"]
            direction TB
            M1["资源监控<br/>Redis · MySQL · ECS"]
            M2["进程监控<br/>异常退出 · 卡死 · 错误日志"]
            M3["服务存活<br/>域名 / 服务器"]
        end

        SVC["Service<br/>spiders-service<br/>集群内 DNS"]
        UTILS["utils/ 公共组件<br/>Redis · MySQL 客户端 · 代理 · Lark · Kafka"]

        WORKLOADS --> MANAGE
        DISPATCH -->|"scrapy.*"| SCRAPY
        DISPATCH -->|"其他 project.*"| OTHER
        DISPATCH -->|"monitor.*"| MON
        SVC --> BOT
    end

    %% ========== 反爬基础设施 ==========
    subgraph INFRA["🛡️ 反爬基础设施"]
        direction LR
        PROXY["HTTP 代理<br/>PROXY_URL"]
        CFRPC["CF 绕过服务<br/>CF_RPC"]
        PW["Playwright<br/>无头浏览器"]
    end

    %% ========== 存储 ==========
    subgraph STORE["💾 存储与消息"]
        direction LR
        REDIS[("Redis<br/>请求队列 · 去重<br/>IP 池 · cookies")]
        MYSQL[("MySQL / RDS<br/>业务数据")]
        MONGO[("MongoDB")]
        KAFKA[["Kafka"]]
        SLS[["阿里云 SLS<br/>日志"]]
    end

    %% ========== 推送与交互 ==========
    subgraph NOTIFY["📣 推送与交互"]
        direction LR
        LARK["Lark / 飞书<br/>群机器人 · 应用机器人"]
        TG["Telegram Bot"]
        MAIL["邮件"]
    end

    USER(("👤 用户"))

    %% ---------- 跨层连线 ----------
    K8SAPI --> W1
    REG -.->|"拉取镜像"| WORKLOADS

    MW --> PROXY
    POLL --> PROXY
    ANTI --> CFRPC
    ANTI --> PW
    W2 -.-> PW
    PROXY --> SRC
    PW --> SRC
    CFRPC --> SRC

    SCH <--> REDIS
    EXT <--> REDIS
    ANTI -->|"写入 IP / cookies"| REDIS
    POLL <--> REDIS
    PL --> MYSQL
    PL --> MONGO
    PL --> KAFKA
    PL --> SLS
    POLL --> MYSQL
    BOT <--> MYSQL

    POLL -->|"告警"| LARK
    POLL --> TG
    POLL --> MAIL
    MON -->|"告警"| LARK
    M1 -.-> REDIS
    M1 -.-> MYSQL

    USER -->|"指令 / 查询"| LARK
    USER --> TG
    LARK -->|"回调"| SVC
    TG -->|"回调"| SVC
    BOT -->|"回复图表 / 结果"| LARK

    %% ---------- 样式 ----------
    classDef src fill:#eef6ff,stroke:#4a8bd6,color:#123
    classDef store fill:#fff6e6,stroke:#d69a2d,color:#321
    classDef notify fill:#eefaf0,stroke:#3aa55a,color:#132
    classDef infra fill:#fdeeee,stroke:#d05050,color:#311
    classDef core fill:#f3efff,stroke:#7a5cd6,color:#213
    class S1,S2,S3,S4,S5,S6 src
    class REDIS,MYSQL,MONGO,KAFKA,SLS store
    class LARK,TG,MAIL notify
    class PROXY,CFRPC,PW infra
    class MANAGE,CFG,DISPATCH core
```

> 图例：实线表示调用或数据流，虚线表示镜像拉取、监控探测等辅助关系，双向箭头表示读写同一份 Redis 状态。
>
> 典型数据流：**采集**（数据源 → 代理 / CF 绕过 → 爬虫）→ **落库**（Redis 队列与去重，MySQL 存业务数据）→ **推送**（Lark / Telegram / 邮件）。机器人则反向接收用户在 Lark / Telegram 中的指令，通过 `spiders-service` 回调到对应端口。

几个关键设计：

- **单一入口、单一镜像**：所有任务都通过 `manage.py -s <project>.<name>` 启动。k8s 里每个任务是同一镜像的一个容器，区别只在启动命令。
- **配置分层**：`config/base.py` 统一从环境变量读取连接信息，`local / test / pre / prod` 各环境类继承自它，运行时由 `-e` 参数选择。
- **Scrapy 分布式**：基于 `scrapy-redis`，请求队列和去重集合放在 Redis 中，支持多实例消费和断点续爬。
- **常驻 + 自调度**：Scrapy 爬虫进程常驻，空闲时由自定义扩展按 `cron_job` 或 `schedule_time` 重新投放种子 URL，不依赖外部定时器。

---

## 目录结构

| 路径 | 说明 |
|---|---|
| `manage.py` | 统一启动入口 |
| `commands/` | 命令行参数解析（`bootstrap`）与任务分发（`run_spider`） |
| `config/` | 分环境配置：`base.py` 公共配置，`local/test/pre/prod.py` 各环境；`exchange.py` 交易所相关配置 |
| `scrapy_spider/` | Scrapy 分布式爬虫工程（见下文 [Scrapy 爬虫](#1-scrapy-爬虫)） |
| `other_spider/` | 非 Scrapy 任务，每个子目录是一个 project，暴露 `run(name)` 函数 |
| `monitor/` | 服务器资源、进程存活/卡死、错误日志、域名存活等监控与告警 |
| `utils/` | 公共工具：Redis / MySQL 客户端、代理、Lark 机器人、Kafka、时间解析等 |
| `tools/` | 辅助小工具（PDF 生成/转换） |
| `.devops/` | CI/CD 流水线定义（镜像构建 + k8s 部署） |
| `k8s.yml` | 主 Deployment `spiders` 及 Service `spiders-service` |
| `playwright.yml` / `tgscan.yml` | 依赖 Playwright 的任务、Telegram 消息监听，各自单独部署 |
| `k8s_once.yml` | 一次性任务（k8s Job） |
| `Dockerfile*` | 业务镜像构建文件（见 [镜像](#镜像)） |
| `pyproject.toml` / `uv.lock` | 依赖声明（Python ≥ 3.11） |
| `requirements_backup.txt` / `requirements.txt` | 基础镜像依赖 / 业务镜像新增依赖 |

---

## 快速开始

```bash
# 1. 安装依赖（任选一种）
uv sync
# 或
pip install -r requirements.txt

# 依赖 Playwright 的任务还需要安装浏览器
playwright install chromium

# 2. 配置环境变量
cp .env.example .env          # .env 已被 .gitignore 忽略
set -a && source .env && set +a

# 3. 本地运行一个任务
python manage.py -e local -s cmc.m
python manage.py -e local -s scrapy.galxe
```

---

## 命令行入口

```bash
python manage.py -e <env> -s <project>.<name> [-t yes|no] [-d YYYYMMDD|now]
```

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-s, --spider` | **必填**。`<project>.<name>`，见下方分发规则 | — |
| `-e, --env` | 运行环境：`local` / `dev` / `test` / `pre` / `prod` | `prod` |
| `-t, --type` | 是否投放历史队列（`yes` / `no`） | `yes` |
| `-d, --date` | 指定采集日期，如 `20200719`；`now` 表示当天 | `now` |

> ⚠️ 不传 `-e` 时默认使用 **生产环境** 配置，本地调试务必显式指定 `-e local`。

参数会写入进程环境变量 `env`、`history_type`、`spider_date`，供配置和爬虫读取。

**分发规则**（`commands/run_spider.py`）：

| `-s` 的值 | 实际执行 |
|---|---|
| `scrapy.<spider_name>` | `scrapy crawl <spider_name>` |
| `monitor.<name>` | `monitor.run(<name>)` |
| `<project>.<name>` | `other_spider.<project>.run(<name>)` |

---

## 两类任务

### 1. Scrapy 爬虫

位于 `scrapy_spider/`，适合有明确请求队列、需要分布式和断点续爬的采集。

| 路径 | 说明 |
|---|---|
| `spiders/` | 爬虫：`galxe`、`dappradar`、`debank`、`lineascan`、`hot_crypto_category/*` |
| `middlewares/` | UA 随机、代理注入、去除自动添加的 `Proxy-Authorization`、失败换代理重试 |
| `extensions/extension.py` | 定时调度扩展 `SpiderInsertStartUrlExtension` |
| `ext_pipelines/` | 输出管道：MySQL（默认启用）、MongoDB、Kafka、阿里云 SLS |
| `items/` | Item 定义 |
| `settings.py` | 全局配置：scrapy-redis 调度器、并发、重试、中间件、管道 |
| `run.py` | 本地 debug 入口 |

**运行机制**

- 调度器 `scrapy_redis.scheduler.Scheduler`，队列 `SpiderStack`，`SCHEDULER_PERSIST = True`。请求队列为 `<name>:requests`，去重集合为 `<name>:dupefilter`。
- 爬虫启动时，扩展按以下优先级投放任务：
  1. `<name>:requests` 非空，则断点续爬；
  2. `redis_key` 队列非空，则直接消费；
  3. 否则把 `start_urls` 写入 `redis_key`。
- 爬虫空闲时（约 5 秒检测一次）判断是否触发下一轮。触发时先清空 `<name>:dupefilter`，再投放种子：
  - `cron_job`：crontab 语法（分 时 日 月 周），只在 `prod` 环境生效，用 Redis key 防止一分钟内重复拉起；
  - `schedule_time`：空闲计数超过该值时触发，按约 5 秒一次计数，`12 * 30` ≈ 30 分钟。配置了 `cron_job` 时忽略此项。
- 默认并发 3、超时 10s、重试 3 次。重定向被禁用，因为重定向通常意味着接口变化或被风控。

**爬虫类属性**

```python
class Galxe(RedisSpider):
    name = 'galxe'
    redis_key = f"{name}:start_url"      # 种子队列
    start_urls = ['https://...']          # 队列为空时用于生成种子
    schedule_time = 12 * 60 * 24          # 间隔调度：约 1 天
    cron_job = "1 14 * * *"               # 定时调度：每天 14:01（二选一）
    proxy = 'china'                       # 代理：False 不走代理；含 http:// 的字符串为自定义代理
    change_ua = True                      # 是否随机 UA
    topic = 'xxx'                         # Kafka topic（启用 Kafka 管道时）
    history_type = False
```

**新增 Scrapy 爬虫**：在 `scrapy_spider/spiders/<site>/` 下新建 spider，按需设置上述属性，然后用 `python manage.py -e local -s scrapy.<name>` 运行。

### 2. 独立任务（other_spider）

`other_spider/` 下每个子目录是一个 project，在 `__init__.py` 中实现 `run(name)`，根据 `name` 分发到具体逻辑：

```python
# other_spider/BK_early_project/__init__.py
def run(spider_name):
    if spider_name == 'run':
        app.run(host='0.0.0.0', port=84)     # 机器人 Web 服务
    elif spider_name == 'ipmonitor':
        IpStore().ipstore_monitor()          # 代理 IP 池维护
    elif spider_name == 'gencookies':
        Gen().gen_loop()                     # 生成绕过 Cloudflare 的 cookies
```

这类任务大致分三种形态：

- **轮询采集 / 告警**：常驻进程，内部循环或用 `schedule` 定时，如 `cmc.m`、`mongrel_dog.list`。
- **机器人服务**：Flask 应用，接收 Lark/Telegram 回调，监听固定端口，见 [对外服务与端口](#对外服务与端口)。
- **反爬辅助**：`ipmonitor`（维护代理 IP 池）、`gencookies`（借助 `CF_RPC` 服务或 Playwright 生成 Cloudflare 的 `cf_clearance`）。

**新增独立任务**：新建 `other_spider/<project>/__init__.py` 并实现 `run(name)`，然后用 `python manage.py -s <project>.<name>` 启动。

---

## 配置与环境

### 运行环境

| `-e` | 配置类 | 说明 |
|---|---|---|
| `local` / `dev` | `LocalConfig` | 本地开发 |
| `test` | `TestConfig` | 测试环境（独立的 Docker 测试集群） |
| `pre` | `PreConfig` | 预发布，部分服务已迁移至香港节点 |
| `prod` | `ProdConfig` | 生产环境（默认） |

### 环境变量

全部连接信息和凭证都从环境变量读取，变量的完整列表、分类和使用模块见 `.env.example`。只需填写要运行的模块用到的变量。

| 类别 | 主要变量 |
|---|---|
| Redis | `REDIS_HOST` `REDIS_PORT` `REDIS_USERNAME` `REDIS_PASSWORD` `REDIS_DB` |
| MySQL | `RDS_HOST` `RDS_PORT` `RDS_USER` `RDS_PASSWORD` |
| 代理 | `PROXY_URL`（`http://user:pass@host:port`） |
| CF 绕过服务 | `CF_RPC` `CF_RPC_HOST` |
| 阿里云 SLS | `ALIYUN_SLS_ENDPOINT` `ALIYUN_ACCESS_KEY_ID` `ALIYUN_ACCESS_KEY_SECRET` `ALIYUN_SLS_PROJECT` `ALIYUN_SLS_LOGSTORE` |
| 推送 | 各模块的 Lark Webhook、Telegram Bot Token、第三方 API Key |

> Scrapy 连接 Redis 时使用 TLS（`rediss://`），见 `scrapy_spider/settings.py`。

---

## 部署

### 镜像

| 文件 | 用途 |
|---|---|
| `Dockerfile` | 主业务镜像。基于预装依赖的基础镜像 `spider:latest`，复制代码并安装 `requirements.txt` |
| `DockerfilePlaywright` | 带 Playwright 浏览器环境的镜像 |
| `Dockerfiletransfer` / `Dockerfiletransferplaywright` | 镜像迁移用 |
| `Dockerfile_backup` | 旧版（带 Google Trends 环境）的备份 |

基础镜像不包含业务代码，只装依赖（`requirements_backup.txt`），这样业务代码更新时只需重建上层。

### Kubernetes

| 文件 | 资源 | 内容 |
|---|---|---|
| `k8s.yml` | Deployment `spiders` + Service `spiders-service` | 主力常驻任务，每个任务一个容器 |
| `playwright.yml` | Deployment `playwright` | 依赖 Playwright 的任务 |
| `tgscan.yml` | Deployment `tgscan` | Telegram 消息监听（`monitor.tgmessage`） |
| `k8s_once.yml` | Job `spiders-once` | 一次性数据任务 |

**新增常驻任务**：在 `k8s.yml` 的 `containers` 中追加一个容器，`command` 写成 `python manage.py -e prod -s <project>.<name>`。需要对外提供服务的，同时在 `spiders-service` 中加端口。

容器统一设置环境变量 `mainex_logs_spider=stdout`，日志输出到标准输出，由集群统一采集。

### CI/CD

流水线定义在 `.devops/`，流程为：

```
git clone (master) → docker build & push (tag = short commit id) → 更新 k8s.yml 镜像 tag → PUT 到 k8s API
```

部署步骤的核心脚本：

```bash
sed -i "s/spider:[^[:space:]]*/spider:$DOCKER_IMAGE_TAG/" k8s.yml
curl -H "Authorization: Bearer <K8S_API_TOKEN>" \
     -H "Content-Type: application/yaml" \
     -X PUT --data-binary "@k8s.yml" \
     https://<K8S_API_HOST>/apis/apps/v1/namespaces/default/deployments/spiders
```

> 受流水线限制，**自动部署只覆盖 `default` 命名空间下的 Deployment `spiders`**。`playwright.yml`、`tgscan.yml`、`k8s_once.yml` 和 Service 变更需要手动 `kubectl apply`。

---

## 对外服务与端口

集群内通过 k8s DNS 访问 `spiders-service`。容器端口和 Service 端口一致。

| 端口 | 服务 | 启动命令 |
|---|---|---|
| 83 | Telegram 热点转发机器人 | `monitor.tginsightbot` |
| 84 | BK 早期项目机器人 | `BK_early_project.run` |
| 88 | SimilarWeb 网站流量查询机器人（Lark） | `similarweb.run` |
| 89 | BK 筛项目草稿机器人 | `bkproject_document.run` |
| 90 | 项目评审机器人 | `project_review.run` |
| 91 | 钱包批量余额查询机器人 | `wallet_balance.run` |
| 92 | Birdeye Find GEMS 机器人 | `birdeye.gems` |
| 93 | BTC Gas 机器人 | `btc_gas.gas` |
| 94 | 市占率走势查询机器人 | `mainex_marketpercent_bot.server` |
| 95 | Input Hub | `input_hub.server` |

<details>
<summary>集群基础设施端口</summary>

| 端口 | 用途 |
|---|---|
| 443 | Nginx（外网入口）/ k8s dashboard（集群内，容器 8443） |
| 6443 | k8s API |
| 5601 | Kibana |
| 8080 / 50000 | Jenkins |
| 2375 / 2376 | Docker in Docker |
| 5000 | Docker Registry |
| 3000 / 96→22 / 5432 | Gitea Web / SSH / 数据库 |
| 86 | Docker CF 绕过服务（内网） |

</details>

---

## 任务清单

以 `k8s.yml` 中实际部署的任务为准，按业务分组：

| 业务 | 任务（`-s` 参数） | 说明 |
|---|---|---|
| CMC 行情策略 | `cmc.m` `cmc.strong` | 基于均线、K 线形态的筛选与告警 |
| 热门板块 | `scrapy.crypto_hot_category` `scrapy.scan_high_exchange_rate` `scrapy.scan_high_exchange_rate_top1000` `scrapy.hot_category_top1000` `hot_category.run` | 先扫描高涨幅币，再按所属板块计数并推送。前两个有依赖关系 |
| 交易所 | `mainex.ccxt` `mainex.coinlist` `mainex.newcoinalert` | 交易所行情、币种列表、新币上线告警 |
| 市占率 | `mainex_marketpercent.run` `mainex_marketpercent_bot.refresh` `mainex_marketpercent_bot.server` | 每日市占率告警与查询机器人 |
| 土狗 / 早期项目 | `mongrel_dog.list` `mongrel_dog.detail` `mongrel_dog.deldata` `mongrel_dog_user_a.run` `BK_early_project.*` `pre_market_alert.run` `birdeye.gems` | DexScreener 新币、盘前市场、早期项目发现 |
| NFT | `opensea.list` `opensea.pending` `opensea.detail` `mintfun.list` `mintfun.detail` `nswap.*` | NFT 列表与 mint 监控 |
| 链上 / 铭文 | `bestinslot.run` `btc_gas.gas` `ethbtc_volume.run` | 铭文市场、BTC Gas、ETH/BTC 成交量 |
| 社媒 / 舆情 | `twitterscan.alert` `twitterscan.insert` `kol_insight.run` `googletrends_api.oldapi` | Twitter 热度、KOL 动态、Google 指数 |
| Web3 平台 | `scrapy.galxe` `dappradar_daily.run` | Galxe 活动、DappRadar 每日数据 |
| 机器人 | `project_review.run` `bkproject_document.run` `wallet_balance.run` `similarweb.run` `input_hub.server` | 见 [对外服务与端口](#对外服务与端口) |
| 反爬辅助 | `gen_coingecko_cf_token.ipmonitor` `gen_coingecko_cf_token.gencookies` | CoinGecko Cloudflare cookies 与 IP 池 |

各模块的细节（数据源、需求方、策略说明）见对应目录下的 `README.md`。

**已停用**：`brc20.*`（项目方已关停，仅 `unisat` 以 Playwright 方式保留）、`crypto_scan.*`（受 Nansen 限制中止）、`premint.*`、`nasen`、`cmc_history`、`coingecko_once.*`（一次性任务）。

---

## 监控

`monitor/` 通过 `python manage.py -s monitor.<name>` 启动：

| 名称 | 作用 |
|---|---|
| `monitor.hardware`（或其他未匹配的名称） | 并发监控 Redis、MySQL、ECS 资源和进程数 |
| `monitor.process_error` | 进程异常退出（`process_dead`）、进程卡死（`process_stuck`）、错误日志（`alllogs`） |
| `monitor.serverlive` | 域名 / 服务器存活检测 |
| `monitor.twitterkol` | Twitter KOL 热门币监控 |
| `monitor.tginsightbot` | Telegram 热点转发机器人（端口 83） |

> 部分宿主机上直接运行的进程不在 k8s 内，需要在宿主机上另起一份 `monitor.hardware` 和 `monitor.process_error`。

---

## 注意事项

- **第三方依赖有定制修改**：`google trends relationwords` 和 `stweet` 用到的第三方库代码经过自定义修改，直接从 PyPI 安装的版本无法正常工作。
- **setuptools 版本**：`setuptools==60.9.0` 会导致 `web3` 安装失败，当前固定为 `68.0.0`。
- **默认生产环境**：`-e` 缺省时为 `prod`，`cron_job` 定时调度也只在 `prod` 下生效。
- **宿主机直接运行**：少数任务仍以 `nohup python manage.py -e prod -s <task> > <task>.log &` 方式运行在宿主机上。迁入 k8s 后应从宿主机下线，避免重复运行。
