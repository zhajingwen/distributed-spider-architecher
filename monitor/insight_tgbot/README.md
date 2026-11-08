### 端口

---
- 开启83端口
- 但是防火墙并未开放83端口
- 通过Nginx来实现路由转发，Nginx端口443
- 回调地址：https://example.com

### 机器人创建流程

---
- 登录telegram，联系botfather机器人，按流程创建机器人
- 对接webhook地址
  - 配置好restful api 并且启动，得是https协议，暴露端口，确定好具体地址，改地址就是webhook的地址
  - 将上面配置好的webhook的地址绑定机器人，提交给telegram服务器，提交成功后，有新的消息就会推送过来
    > 绑定方式：https://www.cnblogs.com/carver/articles/16630823.html or https://cloud.tencent.com/developer/ask/sof/137043
    > 或者官方文档：https://core.telegram.org/bots/api#setwebhook

### 机器人回复消息

---
- 服务器对hook到的消息进行处理，直接给telegram提供的api发起请求，如下示例：
```python
import requests
base_url = 'https://api.telegram.org/bot<TG_BOT_TOKEN_INSIGHT_TGBOT>/{}'
headers = {'Content-Type': 'application/x-www-form-urlencoded'}
bot_token = "<TG_BOT_TOKEN_INSIGHT_TGBOT>"

pd = {
    "chat_id": "chat_id",
    "parse_mode": "Markdown",
    "text": "msg",
    "message_thread_id": "message_thread_id",
    'disable_web_page_preview':True
}
# if message_thread_id is None pop the key
# if not message_thread_id:
#     pd.pop('message_thread_id')
key = 'sendMessage'
url = base_url.format(key)
res = requests.post(url, headers=headers, data=pd)
```
- 按照官方文档提供的标准调用方式，调用即可；应该也存在第三方库包了一层更为简单的调用