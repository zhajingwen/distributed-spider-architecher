[//]: # (### 分阶段执行：)

[//]: # (- 第一阶段：mexcSpider&#40;&#41;.filter_listing_information&#40;&#41;)

[//]: # (> 采集入库（redis）)

[//]: # (- 第二阶段：mexcSpider&#40;&#41;.run&#40;&#41;)

[//]: # (> 去重，清洗，写入csv)

### 分成两大块

---

- 1、爬虫从上币公告中抽取以下信息
```text
['公告发布时间', '公告链接', '公告标题', '代币全称', '代币简称', '币对', '上币时间']
```
> 其中``['代币全称', '代币简称', '币对', '上币时间']` 这四项信息最为关键，其他都是辅助校验信息
> 爬虫数据最终输出两种形式：1、csv文件 2、redis数据库hash结构：coingecko_once:mexc:symbols
> hash结构样例：{"SPT":"['2023-08-05T03:31:30Z', 'https://www.mexc.com/support/articles/17827791509868', 'Voting Result and Listing Arrangement for Kickstarter - SeaPad (SPT)', 'SeaPad ', 'SPT', 'SPT/USDT', '2023-08-05 14:00']"}

- 2、
> 从redis hash 表中（coingecko_once:mexc:symbols）消费，作为任务，调用coingecko搜索接口：
> https://www.coingecko.com/en/search_v2?query=MBD 进行搜索，匹配
> 数据样例：{
    "coins": [
        {
            "thumb": "https://assets.coingecko.com/coins/images/25617/thumb/mbd-transparent_%281%29.png?1696524751",
            "name": "MBD Financials",
            "symbol": "MBD",
            "market_cap_rank": 2799,
            "id": "mbd-financials"
        }
    ],
    "nftContracts": [],
    "markets": [],
    "categories": []
}
> 如果列表不止一个 元素，那么这个就很有可能有歧义，一般来说只会有1个元素
> 将匹配到的数据，加入原始list，拼接成新的value，重新赋值给 hash map 的key，完成更新
> 至此完成了 MEXC到coingeck的关联，刷新了 coingecko_once:mexc:symbols 使其维度更丰富
> 数据导出：导出成csv 字段：[交易所,Token全称,Token简称,CG上的Token简称,交易对,CG--link]
- 3、采集历史数据，数据源来自


### 需要执行三个命令

- 命令分优先级
```shell
# 与coingecko做匹配
python manage.py -e prod -s coingecko_once.mexcmatch
# 将匹配结果导出为csv
python manage.py -e local -s coingecko_once.mexcmatch
# 采集历史交易数据
python manage.py -e local -s coingecko_once.mexctradeinfo
```