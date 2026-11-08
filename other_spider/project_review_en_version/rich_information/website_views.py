import os
import requests
import time
import logging
from traceback import format_exc
from functools import wraps
from datetime import datetime
from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Similarweb Spider')

class WebsiteVisiters:
    def __init__(self, url):
        # 提取出主域名
        domain = url.split('//')[-1]
        domain = domain.split('/')[0].split('?')[0]
        domain = domain.split('.')[-2:]
        domain_name = '.'.join(domain)
        logger.info(f'地址：{url}, 域名：{domain_name}')
        self.domain_name = domain_name

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
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'ConnectionRefusedError' in error:
                            logger.warning(f'{func.__name__} ConnectionRefusedErr')
                        elif 'json.decoder.JSONDecodeError' in error:
                            logger.warning(f'{func.__name__} JSONDecodeErr')
                        elif '响应码错误：408' in error:
                            logger.warning(f'{func.__name__} 响应码错误：408')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待20s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def req(self, url_type):
        """
        发起接口请求
        """
        api_key = os.getenv('SIMILARWEB_API_KEY', '')
        num = 0
        while True:
            current_date = datetime.now().date()
            last_month = current_date - relativedelta(months=(1+num))
            # two_months_ago = current_date - relativedelta(months=(1+num))
            start_date = last_month.strftime("%Y-%m")
            end_date = last_month.strftime("%Y-%m")
            if url_type == 'geo':
                url = f"https://api.similarweb.com/v4/website/{self.domain_name}/geo/total-traffic-by-country?api_key={api_key}&start_date={start_date}&end_date={end_date}&main_domain_only=false&format=json&limit=100&offset=0&asc=true"
            else:
                url = f"https://api.similarweb.com/v1/website/{self.domain_name}/total-traffic-and-engagement/visits?api_key={api_key}&start_date={start_date}&end_date={end_date}&country=world&granularity=monthly&main_domain_only=false&format=json&show_verified=false&mtd=false&engaged_only=false"
            num += 1
            logger.info(f"request: {url}")
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            logger.info(f"respose: {response.status_code} {url}")
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                if num > 3:
                    break
                if response.status_code == 400:
                    error_message = response.json()['meta']['error_message']
                    logger.error(f'{error_message}')
                    logger.info('切换日期重试')
        return

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

    def visit(self):
        """
        最近一个月的流量
        """
        data = self.req('visit')
        if not data:
            logger.error("visit 响应码错误,重试...")
            return
        details = data["visits"]
        content = ""
        for visit in details:
            # 很怪这里的人数是小数
            members = int(visit['visits'])
            members = self.num_transform(members)
            row = f"latest month visiters:  {members}"
            content += row
        return content

    def geo(self):
        """
        不同地区近3月总量
        """
        data = self.req('geo')
        if not data:
            logger.error(f'geo 响应码错误')
            return
        details = data["records"]
        count = 1
        base = "\nThe top 8 country are(latest month):\n{}"
        content = []
        max_length = 0
        for index, i in enumerate(details):
            if index >= 8:
                break
            if len(i["country_name"]) > max_length:
                max_length = len(i["country_name"])
                # print(f'max_length: {max_length}  {i["country_name"]}')
        for i in details:
            # print((max_length - len(i["country_name"])))
            nb_space = (max_length - len(i["country_name"])) * ' '
            members = int(i["visits"])
            members = self.num_transform(members)
            row = "  {} {}({})\n".format(i["country_name"], nb_space, members)
            content .append(row)
            count = count + 1
            if count == 9:
                break
        content_result = base.format("".join(content))
        return content_result

    def visiters(self):
        content_v = self.visit()
        if not content_v:
            content_v = '每月总流量数据请求失败！\n'
        content_g = self.geo()
        if not content_g:
            content_g = '区域流量排行榜数据请求失败！'
        content = content_v + content_g
        return content


if __name__ == '__main__':
    print(WebsiteVisiters("baidu.com").visiters())