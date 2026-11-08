### 2023年11月25号

---

- 衔接MEXC的任务清单，采集历史交易数据
- 将任务来源从文件切换成redis：coingecko_once:mexc:symbols，格式也有变化；格式样例：
```json
{"mexc_url": "https://www.mexc.com/support/articles/17827791509868", "mexc_title": "Voting Result and Listing Arrangement for Kickstarter - SeaPad (SPT)", "name": "SeaPad ", "symbol": "SPT", "pair": "SPT/USDT", "listing_time": "2023-08-05 14:00", "coingecko_match": {"name": "SeaPad", "symbol": "SPT", "id": "seapad"}, "Initial_Listing": true, "markets": [["SPT/USDT", "MEXC", 100.0]]}
```