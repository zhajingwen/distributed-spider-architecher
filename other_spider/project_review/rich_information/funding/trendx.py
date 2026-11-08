import requests
import logging
import json
from retry import retry
from datetime import datetime
from traceback import format_exc
from urllib.parse import urlencode
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Trendx Funding')

class Trendx:
    """
    从下面网站采集融资信息
    https://app.trendx.tech/projects
    """
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num / 1000000000), 2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num / 1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    @retry(tries=2, delay=3)
    def req(self, url, name):
        """
        发起请求
        """
        logger.info(f'Get {url}')
        res = requests.get(url=url, headers=self.headers, proxies=proxies)
        logger.info(f'response {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {name}')
        return res

    def parse_searchresult(self, res, name, type):
        """
        解析出项目在Trendx的ID
        """
        try:
            if type == 'token':
                projectUid = res.json()['data']['rows'][0]['projectUid']
            else:
                projectUid = res.json()['data']['rows'][0]['uid']
            return projectUid
        except:
            logger.warning(f'Trendx {type} 搜不到该项目：{name}')
        return

    def parse_funding_data(self, res, name):
        """
        解析出融资信息
        """
        try:
            capitals = res.json()['data']
        except:
            logger.warning(f'无融资信息 {name}')
            return
        content = []
        for c in capitals:
            financingAt = c['financingAt']
            financingdate = datetime.fromtimestamp(financingAt/1000)
            financingdate = financingdate.strftime('%Y-%m-%d %H:%M:%S')
            amount = c['amount']
            if amount == 0:
                amount = '未公布'
            else:
                amount = self.num_transform(amount)
            investors = c['investors']
            investors = json.loads(investors)
            row = f'\n{financingdate} {amount} \n'
            for investor in investors:
                captital_name = investor['name']
                row += f'{captital_name}\n'
            content.append(row)
        content_funding_info = '\n'.join(content)
        return content_funding_info

    def get_id(self, name):
        params = {
            'name': name,
            'page': 1,
            'rows': 20
        }
        params = urlencode(params)
        search_url = f'https://app.trendx.tech/v1/dao/public/token?{params}'
        search_data = self.req(search_url, name)
        id = self.parse_searchresult(search_data, name, 'token')
        if not id:
            """
            fullName: Success Kid
            page: 1
            rows: 20
            sort: heat1
            order: 2
            """
            params = {
                'fullName': name,
                'page': 1,
                'rows': 20,
                'sort': 'heat1',
                'order': 2
            }
            params = urlencode(params)
            search_url = f'https://app.trendx.tech/v1/dao/public/projects/stars?{params}'
            search_data = self.req(search_url, name)
            id = self.parse_searchresult(search_data, name, 'star')
        return id

    def funding(self, name):
        try:
            id = self.get_id(name)
            if id:
                funding_api_url = f'https://app.trendx.tech/v1/dao/public/projects/{id}/financing'
                funding_data = self.req(funding_api_url, name)
                content = self.parse_funding_data(funding_data, name)
                return content
            return
        except:
            logger.error(f'Trendx 融资信息采集异常: {format_exc()}')
            return

    def combined_rasing(self, data):
        """
        将融资数据组合到date
        """
        name = data['base_info']['代币名称']
        funding_info = data['base_info'].get('融资信息')
        # fundrasing没有获取到数据，才执行该任务
        if not funding_info:
            if not name:
                name = data['base_info']['symbol']
            try:
                content = self.funding(name)
                if content:
                    data['base_info']['融资信息'] = content
            except:
                logger.error(f'trendx 无法提供融资信息：{data}')
        return data