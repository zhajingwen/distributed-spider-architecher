import json
import os
import requests
import time
import logging
import csv
from requests_toolbelt import MultipartEncoder
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.lark_bot_response import Send

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gen Document')

class GenFileId:
    def __init__(self):
        self.redis_cli = redis_cli()
        # Lark user_id -> 显示名称 的映射（JSON），例如 {"abcd1234": "Alice"}
        self.user_id_username_map = json.loads(os.getenv('LARK_USER_NAME_MAP', '{}'))
        self.rds = DataUtils()
        app_id = os.getenv('LARK_APP_ID_BIRDEYE', '')
        app_secret = os.getenv('LARK_APP_SECRET_BIRDEYE', '')
        self.send = Send(app_id, app_secret, 'birdeyegems')

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num/1000000000),2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num/1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    def get_data_and_write_to_csv(self, hours, open_id):
        spider_time = int(time.time()) - hours*60*60
        sql = f'select * from birdeye_gems where spider_time>{spider_time};'
        data_json = self.rds.select(sql)
        # logger.info(f'data_json: {data_json}')
        sorted_data_json = sorted(data_json, key=lambda x: x['vol_24h'], reverse=True)
        # logger.info(f'sorted_data_json: {sorted_data_json}')
        titles = [
            'address',
            'symbol',
            'name',
            'm30',
            'h1',
            'h2',
            'h24',
            'TVL',
            'vol_24h',
            'trades_24h',
            'holders',
            'FDMC',
            'Twitter_followers',
            'security'
        ]
        rows = [titles]
        file_name = f'{open_id}.csv'
        for item in sorted_data_json:
            address = item['address']
            symbol = item['symbol']
            name = item['name']
            m30 = item['m30']
            h1 = item['h1']
            h2 = item['h2']
            h24 = item['h24']
            TVL = self.num_transform(item['TVL'])
            vol_24h = self.num_transform(item['vol_24h'])
            trades_24h = self.num_transform(item['trades_24h'])
            holders = self.num_transform(item['holders'])
            FDMC = self.num_transform(item['FDMC'])
            Twitter_followers = item['Twitter_followers']
            security = item['security']
            row = [
                address,
                symbol,
                name,
                m30,
                h1,
                h2,
                h24,
                TVL,
                vol_24h,
                trades_24h,
                holders,
                FDMC,
                Twitter_followers,
                security
            ]
            rows.append(row)
        with open(file_name, 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)
        logger.info(f'数据已写入csv {file_name}')

    def upload(self, open_id):
        """
        上传文件
        """
        file_name = f'{open_id}.csv'
        url = "https://open.larksuite.com/open-apis/im/v1/files"
        form = {'file_type': 'stream',
                'file_name': file_name,
                'file': (file_name, open(file_name, 'rb'),
                         'text/plain')}  # 需要替换具体的path  具体的格式参考  https://www.w3school.com.cn/media/media_mimeref.asp
        multi_form = MultipartEncoder(form)
        tenant_access_token = self.send.gen_tenant_access_token()
        headers = {
            'Authorization': f'Bearer {tenant_access_token}',
            ## 获取tenant_access_token, 需要替换为实际的token
        }
        headers['Content-Type'] = multi_form.content_type
        response = requests.request("POST", url, headers=headers, data=multi_form)
        code = response.status_code
        if code != 200:
            logger.error(f'上传文件的响应码错误：{code}')
            return
        file_key = response.json()['data']['file_key']
        return file_key

    def get_file_key(self, cmd, open_id):
        # 数据写入csv
        self.get_data_and_write_to_csv(cmd, open_id)
        # 上传文件到服务器，回去回传的文件ID
        file_key = self.upload(open_id)
        return file_key