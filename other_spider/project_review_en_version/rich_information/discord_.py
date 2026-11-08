import requests
import logging
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Discord')

class Discord:

    def __init__(self):
        # 获取discord群组总人数和在线人数接口
        self.api_url_base = 'https://discord.com/api/v9/invites/{}?with_counts=true&with_expiration=true'

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

    @retry(tries=3, delay=3)
    def get_group_members(self, group_id):
        """
        获取群组的总人数和在线人数
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }
        url = self.api_url_base.format(group_id)
        logger.info(f'GET {url}')
        res = requests.get(url, headers=headers, proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        data = res.json()
        # 总人数
        approximate_member_count = data['approximate_member_count']
        approximate_member_count = self.num_transform(approximate_member_count)
        # 在线人数
        approximate_presence_count = data['approximate_presence_count']
        approximate_presence_count = self.num_transform(approximate_presence_count)
        return approximate_member_count, approximate_presence_count

    def discord(self, url):
        """
        从群组链接中解析出群的ID，并且根据该ID获取到群组的人数
        """
        # https://discord.gg/meritcircle
        group_url_split = url.split('/')
        group_id = group_url_split[-1]
        if not group_id:
            group_id = group_url_split[-2]
        total_members, online_members = self.get_group_members(group_id)
        return total_members, online_members