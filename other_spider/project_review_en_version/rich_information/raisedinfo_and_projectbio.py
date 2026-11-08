import requests
import logging
from retry import retry
from lxml import etree
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Raised Info')

class RaisedBio:
    """
    从下面网站采集融资信息
    https://crypto-fundraising.info/projects/Fusionist/
    """
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    @retry(tries=4, delay=3)
    def check_exsist(self, name):
        """
        校验一个币的名称是否存在，存在，那么就返回 crypto-fundraising 网站对应的ID
        不存在返回None
        return: None or id
        """
        formdata = {
            "ptype": "projectsandfunds",
            "search": name
        }
        url = 'https://crypto-fundraising.info/wp-admin/admin-ajax.php?action=custom_acomplete'

        logger.info(f'Post {url}')
        res = requests.post(url=url, headers=self.headers, data=formdata, proxies=proxies)
        logger.info(f'response {res.status_code} url')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {name}')
        origin_data = res.json()[0]
        post_name = origin_data['post_name']
        if post_name == 'null':
            return None
        else:
            return post_name

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

    def project_bio(self, tree):
        """
        获取项目简介
        return: None or str
        """
        pattern = '//div[@class="project-description"]/text()'
        bio = tree.xpath(pattern)
        if bio:
            bio = bio[0].strip()
        return bio

    @retry(tries=4, delay=3)
    def raised_and_bio(self, name):
        """
        根据项目名获取项目的融资额
        return: None or str
        """
        id = self.check_exsist(name)
        if not id:
            logger.warning(f'无融资信息：{name}')
            return
        url = f'https://crypto-fundraising.info/projects/{id}/'
        logger.info(f'Get {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'response {res.status_code} url')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {name}')
        pattern = '//span[@class="abbrusd"]/text()'
        tree = etree.HTML(res.text)
        volume = tree.xpath(pattern)
        if volume:
            volume = volume[0].strip()
            volume = int(volume)
            volume = self.num_transform(volume)
        bio = self.project_bio(tree)
        return volume,bio