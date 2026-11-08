### 每日08：10分统计Mainex创新区涨幅榜



- newcoin_alert.py 新币上线告警；
- 对下面的项目有依赖（playwright运行）
  ```shell
        - name: coingecko-once-mainexallcoins
          image: your-registry.example.com/spider:latest
          command:
            - "python"
            - "manage.py"
            - "-e"
            - "prod"
            - "-s"
            - "coingecko_once.mainexallcoins"
  ```
  - 官方接口不提供 full name，暂不使用；
  - 当前通过 playwright 抓包解析币种链信息接口（见环境变量 EXCHANGE_COIN_CHAIN_URL_KEYWORD）；
  - 