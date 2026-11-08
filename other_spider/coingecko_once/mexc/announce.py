import os
import requests
import json
from datetime import datetime
import re
import logging
from retry import retry
from lxml.etree import HTML
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mexc Extract Listing Info')

headers = {
    'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
}

class Spider:
    """
    从Mexc上币公告中拿到上币清单
    写入两个通道：success.csv + redis coingecko_once:mexc:symbols
    """
    def __init__(self):
        path = 'other_spider/coingecko_once/mexc/'
        # 暂且不用，perPage改成参数10000，直接就拿到全量3646篇
        self.base_api = 'https://www.mexc.com/help/announce/api/en-US/section/15425930840735/articles?page=1&perPage=20'
        with open(f'{path}data.json')as f:
            content = f.read().strip()
            data = json.loads(content)
        # 所有公告的清单
        self.data = data
        PROXY_URL = os.getenv('PROXY_URL', '')
        self.proxy = {
            'https':PROXY_URL,
            'http': PROXY_URL
        }
        self.redis_cli = redis_cli()
        # 请求详情页去重key
        self.duplitude_key = 'coingecko_once:mexc:filterID'
        # 爬虫缓存数据 （set）
        self.data_key = 'coingecko_once:mexc:data'
        self.num = 0
        # hash 缓存去重整理后的数据
        self.symbols_key = 'coingecko_once:mexc:symbols'

    @retry(tries=3,delay=3)
    def detail_request(self, url, data):
        """
        请求详情页
        """
        self.num += 1
        # res = requests.get(url, headers=headers, proxies=self.proxy)
        spiderd_status = self.redis_cli.sismember(self.duplitude_key, url)
        if not spiderd_status:
            res = requests.get(url, headers=headers)
            logger.info(f"{self.num} - {res.status_code}")
            if res.status_code == 200:
                try:
                    self.detail_parse(res.text, data)
                except:
                    logger.info(f'解析失败：{self.num} {url} 跳过！')
                    return
                self.redis_cli.sadd(self.duplitude_key, url)
        else:
            logger.info(f'已采集：{url}')

    def parse_1(self, text, list_data):
        """
        页面格式1
        """
        tree = HTML(text)
        xpath_pattern = '//span[contains(./text(),"Trading in the Innovation Zone:")]'
        span = tree.xpath(xpath_pattern)[0]
        pair = span.xpath("preceding-sibling::a[1]/span/text()")[0]
        zone = span.xpath("following-sibling::span[1]/text()")[0].replace('(UTC)', '').strip()
        data = list_data + [pair, zone]
        return data

    def parse_2(self, text, list_data):
        """
        页面格式2
        """
        tree = HTML(text)
        xpath_pattern = '//div[contains(./text(),"Trading in the Innovation Zone:")]'
        div = tree.xpath(xpath_pattern)[0]
        pair = div.xpath("./strong/a/text()")[0]
        zone = div.xpath("./text()")[0].split('Innovation Zone: ')[-1].replace('(UTC)', '').strip()
        data = list_data + [pair, zone]
        return data

    def parse_3(self, text, list_data):
        """
        页面格式3
        """
        tree = HTML(text)
        # 改规则匹配出 OZONE/USDTTrading in Innovation: 2023-07-28 14:00 (UTC)
        symbol_xpath_patern = '//span[contains(./text(),"Trading in Innovation")]'
        result = tree.xpath(symbol_xpath_patern)
        if result:
            # content = result[0]
            if len(result) == 1:
                trading_time = result[0].xpath('./text()')[0]
                logger.info(trading_time)
                # 'Trading in Innovation: 2023-07-28 14:00 (UTC)'
                trading_time = trading_time.strip().replace('Trading in Innovation: ', '').replace('(UTC)', '').strip()
                pair = result[0].xpath('./b/a/span/text()')[0]
            else:
                pair_usdt = None
                pair_usdt_trading_time = None

                pair_list_info = []

                for row in result:
                    trading_time = row.xpath('./text()')[0]
                    logger.info(trading_time)
                    # 'Trading in Innovation: 2023-07-28 14:00 (UTC)'
                    trading_time = trading_time.strip().replace('Trading in Innovation: ', '').replace('(UTC)',
                                                                                                       '').strip()
                    pair = row.xpath('./b/a/span/text()')[0]
                    pair_list_info.append([pair, trading_time])
                    if 'USD' in pair:
                        pair_usdt = pair
                    if 'USDT' in pair:
                        pair_usdt = pair
                if not pair_usdt:
                    pair = pair_list_info[0][0]
                    trading_time = pair_list_info[0][1]
                else:
                    pair = pair_usdt
                    trading_time = pair_usdt_trading_time
            data = list_data + [pair, trading_time]
        else:
            raise Exception('未匹配到数据')
        return data

    def parse_4(self, text, list_data):
        """
        页面格式4
        """
        tree = HTML(text)
        xpath_pattern = '//span[contains(./text(),"Trading:")]'
        span = tree.xpath(xpath_pattern)[0]
        pair = span.xpath("preceding-sibling::a[1]/span/text()")[0]
        #  Trading: 2023-09-23 08:00(UTC)
        zone = span.xpath("./text()")[0].split('Trading: ')[-1].replace('(UTC)', '').strip()
        # zone = span.xpath("following-sibling::span[1]/text()")[0].replace('(UTC)', '').strip()
        data = list_data + [pair, zone]
        return data

    def parse_5(self, text, list_data):
        """
        页面格式5
        """
        tree = HTML(text)
        xpath_pattern = '//div[contains(./text(),": Trading in the Innovation Zone: ")]'
        div = tree.xpath(xpath_pattern)[0]
        zone = div.xpath("./strong/text()")[0]
        pair = div.xpath("./a/strong/text()")[0]
        # zone = span.xpath("following-sibling::span[1]/text()")[0].replace('(UTC)', '').strip()
        data = list_data + [pair, zone]
        return data

    def parse_6(self, text, list_data):
        """
        页面格式6
        """
        tree = HTML(text)
        xpath_pattern = '//strong[contains(./text(),"Trading:")]'
        strong = tree.xpath(xpath_pattern)[0]
        zone = strong.xpath("./text()")[0].split('Trading: ')[-1].replace('(UTC)', '').strip()
        pair = strong.xpath("preceding-sibling::u[1]/a/text()")[0]
        # zone = span.xpath("following-sibling::span[1]/text()")[0].replace('(UTC)', '').strip()
        data = list_data + [pair, zone]
        return data

    def parse_7(self, text, list_data):
        """
        页面格式7
        """
        try:
            tree = HTML(text)
            xpath_pattern = '//span[contains(./text(), "Trading:")]'
            span = tree.xpath(xpath_pattern)[0]
            zone = span.xpath("./text()")[0].split('Trading: ')[-1].replace('(UTC)', '').strip()
            pair = span.xpath("./strong/a/span/text()")[0]
            # zone = span.xpath("following-sibling::span[1]/text()")[0].replace('(UTC)', '').strip()
            data = list_data + [pair, zone]
            return data
        except:
            data = list_data + ['', '']
            return data

    def detail_parse(self, text, list_data):
        """
        解析数据,落库，落入文件
        """
        try:
            data = self.parse_1(text, list_data)
        except:
            try:
                # 格式2 https://www.mexc.com/support/articles/17827791509296
                data = self.parse_2(text, list_data)
            except:
                try:
                    # 格式3
                    data = self.parse_3(text, list_data)
                except:
                    try:
                        # 格式4
                        data = self.parse_4(text, list_data)
                    except:
                        try:
                            # 格式5
                            data = self.parse_5(text, list_data)
                        except:
                            try:
                                # 格式6
                                data = self.parse_6(text, list_data)
                            except:
                                # 格式7
                                data = self.parse_7(text, list_data)
        # 落入redis
        self.redis_cli.sadd(self.data_key,str(data))

    def listing_information_to_coindata(self, start_timestamp, end_timestamp):
        """
        识别上币公告，采集详情页，解析出name、symbol、上币时间
        """
        for d in self.data['data']['results']:
            createdAt = d['createdAt']
            title = d['title'].strip()
            id = d['id']
            url_en_us = f'https://www.mexc.com/support/articles/{id}'
            # url_zh_cn = f'https://www.mexc.com/zh-CN/support/articles/17827791510113'
            item_type = d['parentSections'][0]['name']
            # 筛选上币数据
            if item_type == "Listing Information":
                dt = datetime.strptime(createdAt, '%Y-%m-%dT%H:%M:%SZ')
                timestamp = int(dt.timestamp())
                # 筛选7-9月的数据
                if (timestamp > start_timestamp) and (timestamp < end_timestamp):
                    # - 存在于标题的过滤规则  本次共146条
                    if ' - ' in title:
                        name_symbol = title.strip().split(' - ')[-1].strip()
                        symbol = name_symbol.split('(')[-1].split(')')[0]
                        if symbol != 'USDT':
                            name =  name_symbol.split('(')[0]
                            row = [createdAt,url_en_us,title,name,symbol]
                            self.detail_request(url_en_us, row)
                    # - 不存在于标题的过滤规则
                    else:
                        if 'of' in title:
                            # 剔除Introduction of 开头的数据
                            match_result = re.match("^Introduction of", title)
                            # 剔除后还剩两条
                            if not match_result:
                                if '(' in title:
                                    name_symbol = title.split('for')[-1].strip()
                                    symbol = name_symbol.split('(')[-1].split(')')[0]
                                    name = name_symbol.split('(')[0]
                                    row = [createdAt, url_en_us, title, name, symbol]
                                    self.detail_request(url_en_us, row)
                        else:
                            # 存在()的
                            if '(' in title:
                                if 'Perpetual Futures' in title:
                                    continue
                                elif 'for' in title:
                                    name_symbol = title.split('for')[-1].strip()
                                    symbol = name_symbol.split('(')[-1].split(')')[0]
                                    name = name_symbol.split('(')[0]
                                    row = [createdAt, url_en_us, title, name, symbol]
                                    self.detail_request(url_en_us, row)
                                else:
                                    if ' List ' in title and 'in' in title:
                                        name_symbol = title.split('List')[-1].strip().split(' in ')[0]
                                        symbol = name_symbol.split('(')[-1].split(')')[0]
                                        name = name_symbol.split('(')[0]
                                        row = [createdAt, url_en_us, title, name, symbol]
                                        self.detail_request(url_en_us, row)
                                    elif ' Launchpad Listing ' in title:
                                        name_symbol = title.split(' Launchpad Listing ')[0].strip()
                                        symbol = name_symbol.split('(')[-1].split(')')[0]
                                        name = name_symbol.split('(')[0]
                                        row = [createdAt, url_en_us, title, name, symbol]
                                        self.detail_request(url_en_us, row)
                                    elif ' Will List ' in title:
                                        pass
                                    elif 'Will Launch the Launchpad with ' in title:
                                        pass
                                    elif 'MEXC Will Change ' in title:
                                        pass
                                    else:
                                        pass
                            else:
                                logger.info(title)

    def merge_repeated_coin(self):
        """
        去重，剔除重复的币，且提出重复中数据不完整的；写入self.symbols_key
        self.symbols_key 作为数据处理的中间存储器，hash
        """
        # 刷新表，去重，且仅保留有全部字段信息的行
        data = self.redis_cli.smembers(self.data_key)
        if not data:
            logger.info('coingecko_once:mexc:data 无数据，跳出')
            return
        # 如果这里有数据，说明该方法已经执行过了，不需要反复执行
        data_symbols_key = self.redis_cli.hgetall(self.symbols_key)
        if data_symbols_key:
            return
        for row in data:
            # self.redis_cli.sadd(self.data_key,row)
            row_eval = eval(row)
            symbol = row_eval[-3]
            if not symbol.strip():
                logger.info(f'symbol为空：{row_eval}')
                continue
            # 校验存在的数据是否是缺失数据
            # 存在更新
            if self.redis_cli.hexists(self.symbols_key, symbol):
                old_row = self.redis_cli.hget(self.symbols_key, symbol)
                old_row = eval(old_row)
                # 如果hash表内的数据是不完整的，进行替换
                if not old_row[-2]:
                    self.redis_cli.hset(self.symbols_key, symbol, row)
            # 不存在新数据入库
            else:
                self.redis_cli.hset(self.symbols_key, symbol, row)

    def run(self, start_timestamp, end_timestamp):
        """
        从上币公告中抽取，name,sumbol,上币时间
        """
        # 先将数据写入 self.data_key
        self.listing_information_to_coindata(start_timestamp, end_timestamp)
        # 再从 self.data_key 捞数据清理，去重
        # 数据写入 self.symbols_key
        self.merge_repeated_coin()