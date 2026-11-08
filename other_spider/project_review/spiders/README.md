- dextools_spider.py是核心币信息搜集模块，所有的币渠道币的信息也在这里整合
- dextools_spider.py 依赖cmc_spider.py补充信息维度
  > 由于dextools有CLOUDflare验证，需要依赖BK_early_project这个项目生成签名cookies
- cmc_spider.py并不直接处理任务输入的cmc链接，而是解析出链接token address 生成任务塞入redis提交给dextools爬虫处理
- goplus.py 通过token地址采集合约检测的相关信息，被dextools_spider.py调用
  > 在dextools_spider.py中get_detail_data方法调用

- coingecko爬虫需要绕过CLOUDflare，故需要依赖 coingecko-ipmonitor 和 coingecko-gencookies