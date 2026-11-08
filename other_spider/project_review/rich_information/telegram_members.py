import requests
import logging
from retry import retry
from lxml.etree import HTML
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Telegram')

class Telegram:

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
    def members(self, url):
        """
        获取群组的总人数和在线人数
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }
        logger.info(f'GET {url}')
        res = requests.get(url, headers=headers, proxies=proxies)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        tree = HTML(res.text)
        pattern = '//div[@class="tgme_page_extra"]/text()'
        content = tree.xpath(pattern)
        if not content:
            return
        content = content[0].strip()
        # 5 662 members, 292 online  也有一种可能性，一个人都没有(一个都没有显示：39989subscribers 格式有所差异)
        if 'subscribers' in content:
            total_members = content.replace(' ', '').replace('subscribers', '')
            # 这种情况是一个在线的都没有
            online_members = 0
        else:
            content = content.split(' members, ')
            total_members = content[0].strip()
            total_members = total_members.replace(' ','')
            online_members = content[1].replace('online', '').strip()
            online_members = online_members.replace(' ', '')
            # 在线人数
            online_members = self.num_transform(int(online_members))
        # 总人数 格式化
        total_members = self.num_transform(int(total_members))
        return total_members, online_members