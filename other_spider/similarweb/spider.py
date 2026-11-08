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

class Spider:
    def __init__(self, domain_name):
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
            two_months_ago = current_date - relativedelta(months=(3+num))
            start_date = two_months_ago.strftime("%Y-%m")
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
            elif response.status_code == 404:
                return 404
            else:
                if num > 3:
                    break
                if response.status_code == 400:
                    error_message = response.json()['meta']['error_message']
                    logger.error(f'{error_message}')
                    logger.info('切换日期重试')
        return

    def visit(self):
        """
        每个月的总流量
        """
        data = self.req('visit')
        if not data:
            logger.error("visit 响应码错误,重试...")
            return
        if data == 404:
            return data
        details = data["visits"]
        content = ""
        for visit in details:
            row = "{}  The total visit number is:  {}\n".format(visit['date'], self.num_transform(int(visit['visits'])))
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
        if data == 404:
            return data
        details = data["records"]
        count = 1
        base = "\nThe top 8 country are(3month):\n{}"
        content = []
        max_length = 0
        total_3m_visitors = 0
        for index, i in enumerate(details):
            if index >= 8:
                break
            if len(i["country_name"]) > max_length:
                max_length = len(i["country_name"])
                logger.info(f'max_length: {max_length}  {i["country_name"]}')
            total_3m_visitors += int(i["visits"])
        for i in details:
            country_name = i["country_name"]
            visits = int(i["visits"])
            nb_space = (max_length - len(country_name) + 3) * ' '
            percent = f'{nb_space}{int((visits/total_3m_visitors)*100)}%'
            row = "  {} {}({}){}\n".format(country_name, nb_space, self.num_transform(visits), percent)
            content .append(row)
            count = count + 1
            if count == 9:
                break
        content_result = base.format("".join(content))
        return content_result

    def check_Capabilities(self):
        """
        查询账户api 余额
        """
        try:
            url = 'https://api.similarweb.com/capabilities?api_key=' + os.getenv('SIMILARWEB_API_KEY', '')
            res = requests.get(url)
            logger.info(f'check capabilities: {res.status_code}')
            data = res.json()
            remaining_hits = data['remaining_hits']
            # similarweb机器人每次交互会调用两次api，消耗2积分
            remaining_hits = int(remaining_hits/2)
            return remaining_hits
        except:
            return '余量查询失败'

    def run(self):
        content_v = self.visit()
        if content_v == 404:
            return f'{self.domain_name}  未收录，无流量数据'
        if not content_v:
            content_v = '每月总流量数据请求失败！\n'
        content_g = self.geo()
        if not content_g:
            content_g = '区域流量排行榜数据请求失败！'
        content = content_v + content_g
        capabilities = self.check_Capabilities()
        capabilities = f'\n剩余调用次数：{capabilities}'
        content += capabilities
        return content