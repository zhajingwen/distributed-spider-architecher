import os
import requests
import json
from requests_toolbelt import MultipartEncoder

class FileUpload:
    def gen_tenant_access_token(self):
        """
        生成 tenant_access_token
        """

        url = 'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal'
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        data = {
            "app_id": os.getenv('LARK_APP_ID_BKPROJECT_DOCUMENT', ''),
            "app_secret": os.getenv('LARK_APP_SECRET_BKPROJECT_DOCUMENT', '')
        }
        res = requests.post(url, headers=headers, data=json.dumps(data))
        print(res.status_code)
        # 过期时间 7200 s  2H
        # {'code': 0, 'expire': 7200, 'msg': 'ok', 'tenant_access_token': '<TENANT_ACCESS_TOKEN>'}
        print(res.json())

    def upload(self):
        url = "https://open.larksuite.com/open-apis/im/v1/files"
        form = {'file_type': 'stream',
                'file_name': 'text.txt',
                'file': ('text.txt', open('newtest.txt', 'rb'),
                         'text/plain')}  # 需要替换具体的path  具体的格式参考  https://www.w3school.com.cn/media/media_mimeref.asp
        multi_form = MultipartEncoder(form)
        headers = {
            'Authorization': os.getenv('LARK_TENANT_ACCESS_TOKEN', ''),
            ## 获取tenant_access_token, 需要替换为实际的token
        }
        headers['Content-Type'] = multi_form.content_type
        response = requests.request("POST", url, headers=headers, data=multi_form)
        #   # 20240123124306EB6778E22F9AA6AEAB9E
        print(response.headers['X-Tt-Logid'])  # for debug or oncall
        # b'{"code":0,"data":{"file_key":"file_v3_007c_9f3b568d-7a9d-40aa-b473-94083b2e785h"},"msg":"success"}'
        print(response.content)  # Print Response
