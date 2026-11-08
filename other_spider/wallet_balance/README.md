# 批量获取钱包余额机器人


***方案一：debank官方API （由于资费较贵，放弃）***

---

- API账户相关信息
```text
User account  user@example.com
Access key  ff04b8c566313a0f71b41665e95ef561674bfc77
Rate limit  100 requests per second
IP whitelist  None
```
- API 调用：
  - 官方文档：https://docs.cloud.debank.com/en/readme/api-pro-reference/user
  - user balance
    ```shell
    curl -X 'GET' \
  'https://pro-openapi.debank.com/v1/user/total_balance?id=0x5853ed4f26a3fcea565b3fbc698bb19cdf6deb85' \
  -H 'accept: application/json'\
  -H 'AccessKey: YOUR_ACCESSKEY'

    ```
  - 资费：200U/月
  - 充值通道：https://cloud.debank.com/open-api
  


***方案二：de.fi爬虫接口***

---

- 官网：https://de.fi
- 通过该地址能够触发ajax数据加载：https://de.fi/account/0x43bd4ec2589944530af4f3ca35f23efdd3d2f900/dashboard/portfolio-overview
- ajax地址：https://api.de.fi/v1/account/sse?addresses%5B%5D=0x43bd4ec2589944530af4f3ca35f23efdd3d2f900&chains%5B%5D=1&chains%5B%5D=2&chains%5B%5D=3&chains%5B%5D=4&chains%5B%5D=5&chains%5B%5D=6&chains%5B%5D=7&chains%5B%5D=8&chains%5B%5D=13&chains%5B%5D=14&chains%5B%5D=17&chains%5B%5D=20&chains%5B%5D=31&chains%5B%5D=47&chains%5B%5D=48&chains%5B%5D=49&events%5B%5D=balances
- 响应体类型：event-stream
- 响应体样例
  ```text
  id: 16
  data: {"0x43bd4ec2589944530af4f3ca35f23efdd3d2f900":{"address":"0x43bd4ec2589944530af4f3ca35f23efdd3d2f900","tokens":[{"decimalsAmount":"0.000584968099999973","amount":"584968099999973","address":"0x43BD4eC2589944530aF4f3CA35F23Efdd3d2F900","price":3940.05,"totalValue":2.3048035624048935,"token":{"address":"0x0000000000000000000000000000000000000000","displayName":"ETH","decimals":18,"symbol":"ETH","name":"Ethereum","chainId":47,"icon":"https://icons.de.fi/ethereum/coingecko.webp","coingeckoId":"ethereum"}}],"totalValue":2.3048035624048935,"errors":[]}}
  event: system
  id: -1
  data: {}
  16.376308098958017
  ```
  
***方案三：基于debank数据的第三方接口，收费，但是便宜（备选）***

---

- 地址：https://rapidapi.com/rainapi-rainapi-default/api/debank-unofficial-wallet-portfolio-balance-api
- 测试接口地址：https://debank-unofficial-wallet-portfolio-balance-api.p.rapidapi.com/user/total_balance?address=0x43bd4ec2589944530af4f3ca35f23efdd3d2f900
- 资费详情：https://rapidapi.com/rainapi-rainapi-default/api/debank-unofficial-wallet-portfolio-balance-api/pricing