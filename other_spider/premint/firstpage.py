import requests
import logging
import time
import csv
import os
from traceback import print_exc
from functools import wraps
from lxml import etree
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PREMINT')

class Spider:
    def __init__(self, id):
        """
        id: burginators    capies
        """
        self.headers = {
            'accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-encoding':'gzip',
            'accept-language':'zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7',
            'cache-control':'max-age=0',
            # 'cookie':'<COOKIE_PREMINT>',
            'dnt':'1',
            'sec-ch-ua':'"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile':'?0',
            'sec-ch-ua-platform':'"macOS"',
            'sec-fetch-dest':'document',
            'sec-fetch-mode':'navigate',
            'sec-fetch-site':'none',
            'sec-fetch-user':'?1',
            'upgrade-insecure-requests':'1',
            'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        self.url = f'https://www.premint.xyz/{id}/'
        self.id = id
        self.titles = ['合集名','推特链接','TW粉丝数','项目介绍','官网链接',
                       '铸造总量（抽奖数量）','注册截止时间','mint开始时间','Mint价格','合约地址','premint链接']


    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10
        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.error(f'{func.__name__}网络请求失败，重试...')
                        print_exc()
                        retry_num += 1
                        if retry_num > num:
                            logger.error('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(20)
                return res
            return wrapper
        return recive_func

    @retry(999)
    def req(self):
        """
        send request
        """
        res = requests.get(self.url,headers=self.headers,proxies=proxies)
        try:
            path = self.parse(res)
            return path
        except:
            logger.error('parse error')
            print_exc()

    def parse(self, response):
        """
        parse page
        """
        logger.info(f'{response.status_code}')
        tree = etree.HTML(response.text)
        register_closed = self.parse_machine(tree, '//*[@id="st-container"]/div/div/div/section[2]/div/div/div[1]/div[2]/div[1]/span/text()')
        mint_date = self.parse_machine(tree, '//*[@id="st-container"]/div/div/div/section[2]/div/div/div[1]/div[2]/div[2]/span/text()')
        pattern = '//div[@class="col-6 col-lg-4 mb-4"]/span/text()'
        total_supply = self.parse_machine(tree, pattern, 'NFTs')

        pattern = '//*[@id="st-container"]/div/div/div/section[2]/div/div/div[1]/div[2]/div[7]/span/a/@href'
        twitter_url = self.parse_machine(tree, pattern)
        pattern = '//*[@id="st-container"]/div/div/div/section[2]/div/div/div[1]/div[2]/div[7]/span/span/text()'
        twitter_fans = self.parse_machine(tree, pattern)
        if 'twitter' not in twitter_url:
            twitter_url = ''
            twitter_fans = ''
        pattern = '//div[@class="mr-lg-5"]//text()'
        introduce = self.parse_machine(tree, pattern)
        pattern = '//div[text()="Official Link"]/following-sibling::span/a/@href'
        website = self.parse_machine(tree, pattern)
        if 'https://' not in website:
            website = 'https://www.premint.xyz'+website
        pattern = '//div[text()="Mint Price "]/following-sibling::span/text()'
        mint_price = self.parse_machine(tree, pattern)
        data = [self.id,twitter_url,twitter_fans,introduce,website,total_supply,
                register_closed,mint_date,mint_price,'',self.url]
        print(data)
        path = os.getcwd()
        logger.info(f'path: {path}')
        with open(f'{path}/{self.id}.csv', 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows([self.titles,data])
        # return data
        return path

    def parse_machine(self, tree, pattern, value_type=None):
        """
        extract all values abstract
        """
        value = tree.xpath(pattern)
        if value_type == None:
            if value:
                # print(value)
                # value = value[0].strip()
                new_value = []
                for i in value:
                    if i.strip():
                        new_value.append(i.strip())
                new_value = ''.join(new_value).strip()
                value = new_value.replace('\n',' ')
                value = value.replace('                                                                                       ',' ')
            else:
                value = ''
        else:
            # print(value)
            for i in value:
                if value_type in i.strip():
                    return i.strip()
        return value


if __name__ == '__main__':
    name = input('input id please: ').strip()
    Spider(name).req()