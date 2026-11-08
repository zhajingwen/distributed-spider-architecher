### lark 机器人
- 文档： https://open.larksuite.com/apps/<LARK_APP_ID_BK_EARLY_PROJECT>/baseinfo
- APP ID <LARK_APP_ID_BK_EARLY_PROJECT>
- APP Secret  <LARK_APP_SECRET_BK_EARLY_PROJECT>

### Nginx 配置路由
```commandline
        location /lark {
            # 保留代理之前的host 包含客户端真实的域名和端口号
            proxy_set_header    Host  $host;
            # 保留代理之前的真实客户端ip
            proxy_set_header    X-Real-IP  $remote_addr;
            # 这个Header和X-Real-IP类似，但它在多级代理时会包含真实客户端及中间每个代理服务器的IP
            proxy_set_header    X-Forwarded-For  $proxy_add_x_forwarded_for;
            # 表示客户端真实的协议（http还是https）
            proxy_set_header X-Forwarded-Proto $scheme;
            # 指定修改被代理服务器返回的响应头中的location头域跟refresh头域数值
            # 如果使用"default"参数，将根据location和proxy_pass参数的设置来决定。
            # proxy_redirect [ default|off|redirect replacement ];
            proxy_redirect off;
            proxy_pass http://localhost:84;
        }
```
- 本地服务 84 端口 
```commandline
from flask import Flask

app = Flask(__name__)

@app.route('/lark')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=84)
```
- 接受回调验证
```commandline
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/lark', methods=['GET', 'POST'])
def hello_world():
    print(request.headers)
    content_type = request.headers.get('Content-Type')
    if 'application/json' in content_type:
        data = request.get_json()
        print(data)
        challenge = data['challenge']
        return jsonify({'challenge': challenge})
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=84)
```
- 回调验证请求体
```commandline
{'challenge': 'f13dddb2-4b0d-47fa-acce-3611d65cb5f9', 'token': '<LARK_VERIFY_TOKEN_BK_EARLY_PROJECT>', 'type': 'url_verification'}
```
- Verification Token
> <LARK_VERIFY_TOKEN_BK_EARLY_PROJECT>
- 接收消息（消息体）
```commandline
{'schema': '2.0', 'header': {'event_id': '<EVENT_ID>', 'token': '<LARK_VERIFY_TOKEN_BK_EARLY_PROJECT>', 'create_time': '1682237623558', 'event_type': 'im.message.receive_v1', 'tenant_key': '<TENANT_KEY>', 'app_id': '<LARK_APP_ID_BK_EARLY_PROJECT>'}, 'event': {'message': {'chat_id': '<CHAT_ID>', 'chat_type': 'p2p', 'content': '{"text":"[奸笑]"}', 'create_time': '1682237623298', 'message_id': '<MESSAGE_ID>', 'message_type': 'text'}, 'sender': {'sender_id': {'open_id': '<OPEN_ID>', 'union_id': '<UNION_ID>', 'user_id': '<USER_ID>'}, 'sender_type': 'user', 'tenant_key': '<TENANT_KEY>'}}}
```
- 接收消息与回复消息是完全分离的两个接口，当接收到消息的时候，webserver程序只需要回复一个包含200状态码的任何消息体即可；而回复消息需要调用另外的接口
- 获取tenant_access_token （有效期为2小时）
```commandline
import requests


url = 'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal'

headers = {
    "Content-Type":"application/json; charset=utf-8",
}


data = {
    "app_id": "<LARK_APP_ID_BK_EARLY_PROJECT>",
    "app_secret": "<LARK_APP_SECRET_BK_EARLY_PROJECT>"
}

res = requests.post(url,headers=headers,json=data)
print(res.text)

```

### twitter采集

---

- 依赖第三方项目：https://github.com/markowanga/stweet
  - 新的参考 https://github.com/trevorhobenshield/twitter-api-client  该项目需要登录个人账户，但是在服务器无法登录成功
- 修改第三方项目 stweet/raw_output/print_raw_output.py
- 修改第三方项目 stweet/get_user_runner/get_users_runner.py
- 具体的修改可以直接参考Macos <site-packages>/stweet

- 返回的数据样例
```commandline
<class 'dict'> {'object_type': 'UserRaw', 'download_datetime': '2023-04-26T11:07:04.955028+08:00', 'raw_value': {'__typename': 'User', 'id': 'VXNlcjoxMDg3Mjg5MzY1NTQ0NTM0MDE2', 'rest_id': '1087289365544534016', 'affiliates_highlighted_label': {}, 'legacy': {'created_at': 'Mon Jan 21 10:02:40 +0000 2019', 'default_profile': True, 'default_profile_image': False, 'description': '🇵🇱 Professional Tennis Player | Trying to put this yellow fluffy thing between the lines.  | #teamSwiatek', 'entities': {'description': {'urls': []}, 'url': {'urls': [{'display_url': 'igaswiatek.pl', 'expanded_url': 'https://igaswiatek.pl/', 'url': 'https://t.co/Kx1aAm4pUx', 'indices': [0, 23]}]}}, 'fast_followers_count': 0, 'favourites_count': 1524, 'followers_count': 442008, 'friends_count': 47, 'has_custom_timelines': True, 'is_translator': False, 'listed_count': 1050, 'location': 'Warszawa, Polska', 'media_count': 643, 'name': 'Iga Świątek', 'normal_followers_count': 442008, 'pinned_tweet_ids_str': [], 'profile_banner_url': 'https://pbs.twimg.com/profile_banners/1087289365544534016/1662703962', 'profile_image_url_https': 'https://pbs.twimg.com/profile_images/1386962724492648449/tvU49FF4_normal.jpg', 'profile_interstitial_type': '', 'protected': False, 'screen_name': 'iga_swiatek', 'statuses_count': 1186, 'translator_type': 'none', 'url': 'https://t.co/Kx1aAm4pUx', 'verified': False, 'withheld_in_countries': []}, 'super_follow_eligible': False, 'super_followed_by': False, 'super_following': False, 'legacy_extended_profile': {}, 'is_profile_translatable': False}}
```
- 伪代码
```commandline
import stweet as st
import json


def try_user_scrap():
    user_task = st.GetUsersTask(['babydogecoin'])
    output_print = st.PrintRawOutput()
    res = st.GetUsersRunner(get_user_task=user_task, raw_data_outputs=[output_print]).run()
    user_content = res[1][0][0]
    if user_content:
        user_content = json.loads(user_content)
        print(type(user_content),user_content)

if __name__ == '__main__':
    try_user_scrap()
```
- 感觉得需要建一个地址和名称的映射表

- 需要在lark应用管理后台，将服务器IP加入白名单
- 需要自定义 get_users_runner.py  和 print_raw_output.py