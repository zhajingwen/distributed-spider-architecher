import requests as requests_ori
from curl_cffi import requests
import time
import logging
import json
import csv
import os
from traceback import format_exc
from datetime import datetime
from retry import retry
from requests_toolbelt import MultipartEncoder
from .send_message import Send
from utils.redisdb import redis_cli
from .twitter import Twitter
from .transaction_risk.goplus import GoplusRisk
from .transaction_risk.quickintel import Quickintel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gen Document')

class Spider:
    def __init__(self, open_id, user_id):
        self.open_id = open_id
        self.user_id = user_id
        self.redis_cli = redis_cli()
        self.cookies_store = 'bk-early:cookies'
        self.dextools_search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        self.send = Send()
        self.goplus = GoplusRisk()
        self.quickintel = Quickintel()
        # Lark user_id -> 显示名称 的映射（JSON），例如 {"abcd1234": "Alice"}
        self.user_id_username_map = json.loads(os.getenv('LARK_USER_NAME_MAP', '{}'))

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

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hold
        """
        while True:
            cookie_json = self.redis_cli.spop(self.cookies_store)
            if not cookie_json:
                logger.warning('当前没有可调用的cookies,等待...')
                time.sleep(5)
                continue
            cookie_dict = json.loads(cookie_json)
            # cookie超过有效期，那么久重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30 * 60:
                pass
                # logger.info(f'该cookies已失效：{cookie_dict}')
            # 如果是有效期内的，那么就再放回去
            else:
                return cookie_dict

    @retry(tries=100, delay=3)
    def req(self, url):
        """
        通过搜索接口获取到代币的详情
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        headers = {
            "Referer": "https://www.dextools.io/app/cn/pairs",
            'User-Agent': cookie_dict['ua'],
        }
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        logger.info(f'GET: {url}')
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101", cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome101")
        logger.info(f'response {res.status_code}: {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code} {url} {cookie_dict}')
        else:
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def get_data_and_write_to_csv(self, origin_url):
        """
        从dextools获取代币详情
        从twitter获取粉丝数
        从quickintel 和 goplus获取合约检测结果
        数据写入csv
        """
        if len(origin_url) == 44 or len(origin_url) == 42:
            address = origin_url
        else:
            # 抽取出address
            address = origin_url.split('pair-explorer/')[-1].replace('/','').strip()
            # 有些URL会带时间戳
            address = address.split('?')[0]
        url = self.dextools_search_url.format(address)
        res = self.req(url)
        data = res.json()['results']

        deploy_day = None
        totalSupply = None
        token_metrics = None
        links = None
        twitter_followers_count = '-'
        data = data[0]

        token = data.get('token')
        price = data.get('price')
        chain = data['id']['chain']
        if token:
            token_metrics = token.get('metrics')
            if token_metrics:
                totalSupply = token_metrics.get('totalSupply')
            links = token.get('links')

        # 推荐日期
        current_date = datetime.now()
        recomand_date = current_date.strftime("%-m.%-d")
        # 推荐人
        recomand_user = self.user_id_username_map.get(self.user_id, '')
        logger.info(f'用户名：{self.user_id} {recomand_user} ;')
        # 项目名称
        # name = data['name']
        symbol = data['symbol']
        if 'http' in origin_url:
            imo = origin_url
        else:
            imo = f'https://www.dextools.io/app/cn/ether/pair-explorer/{origin_url}'
        # 合约部署时间
        creationTime = data.get('creationTime')
        if creationTime:
            # 当前时间
            current_time = datetime.now()
            # 目标时间
            target_time = datetime.strptime(creationTime, "%Y-%m-%dT%H:%M:%S.%fZ")
            # 计算时间差
            time_difference = current_time - target_time
            deploy_day = f'{time_difference.days}d'
        # 流动性池大小
        LIQUIDITY = data['metrics']['liquidity']
        LIQUIDITY = self.num_transform(LIQUIDITY)
        # 总市值
        TOTALMKTCAP = None
        if price and totalSupply:
            TOTALMKTCAP = price * totalSupply
        TOTALMKTCAP = self.num_transform(TOTALMKTCAP)
        # 24小时链上交易额
        VOLUME24H = data.get('volume')
        VOLUME24H = self.num_transform(VOLUME24H)
        # 每周平均交易人数
        Txs24H = data.get('swaps')
        if Txs24H:
            Txs24H = self.num_transform(Txs24H)
            Txs24H = f'{Txs24H}(24h)'
        # twitter粉丝量
        try:
            if links:
                twitter_url = links.get('twitter')
                if twitter_url:
                    twitter_followers_count = Twitter().run(twitter_url)
                    twitter_followers_count = f'TW {twitter_followers_count}'
        except:
            logger.error(f'twitter数据补充异常：{data}，{format_exc()}')
        # 合约地址
        token_address_origin = data['id']['token']
        token_address = f'{chain}: {token_address_origin}'
        # 合约风险
        # 是否以放弃合约
        try:
            is_contract_renounced = token['audit']['is_contract_renounced']
        except:
            is_contract_renounced = False
        if is_contract_renounced:
            transaction_risk = '已放弃合约；'
        else:
            transaction_risk = ''
        # 合约检测 goplus
        goplus_risk_content = self.goplus.check_risk(token_address_origin, chain)
        if goplus_risk_content:
            transaction_risk += f'goplus: {goplus_risk_content}; '
        # 合约检测 quickintel
        quickintel_risk_content = self.quickintel.quickintel(token_address_origin, chain)
        if quickintel_risk_content:
            transaction_risk += f'quickintel: {quickintel_risk_content}'
        row = [
            recomand_date,
            recomand_user,
            symbol,
            imo,
            deploy_day,
            LIQUIDITY,
            TOTALMKTCAP,
            VOLUME24H,
            Txs24H,
            twitter_followers_count,
            token_address,
            transaction_risk,
            '',
            ''
        ]
        titles = [
            '推荐日期',
            '推荐人',
            '项目名称',
            'imo',
            '合约部署时间',
            '流动性池大小',
            '总市值',
            '24小时链上交易额',
            'weekly trade per dex',
            '社群活跃度(Twitter、Telegram、Discord)',
            '合约地址',
            '合约检测风险(写具体描述)',
            '核心上涨逻辑',
            '概念',
        ]
        # 存在则追加写入
        file_name = f'{self.user_id}.csv'
        if os.path.exists(f'{self.user_id}.csv'):
            with open(file_name, 'a', encoding='utf-8-sig', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(row)
            logger.info('数据已写入csv')
        else:
            with open(file_name, 'w', encoding='utf-8-sig', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows([titles, row])
            logger.info(f'数据已写入csv {file_name}')

    def upload(self):
        """
        上传文件
        """
        file_name = f'{self.user_id}.csv'
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
        response = requests_ori.request("POST", url, headers=headers, data=multi_form)
        code = response.status_code
        if code != 200:
            logger.error(f'上传文件的响应码错误：{code} {response.text}')
            return
        file_key = response.json()['data']['file_key']
        return file_key

    def run(self, content):
        # https://www.dextools.io/app/en/bnb/pair-explorer/0x429e89b78fc5249ddd5bc048c4d914ad720cf4e8
        for row in content.strip().split('\n'):
            url = row.strip()
            logger.info(f'开始处理：{url}')
            # 数据写入csv
            self.get_data_and_write_to_csv(url)
        # 上传文件到服务器，回去回传的文件ID
        file_key = self.upload()
        if file_key:
            # file_key = 'file_v3_007d_9d83c52b-0ac6-47b8-bc96-6d0f89f91c0h'
            self.send.send(self.open_id, file_key, 'file')

