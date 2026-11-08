import time
import requests
import logging
import re
import os
from math import ceil
from lxml import etree
from retry import retry
from hashlib import md5
from datetime import datetime
from utils.proxy_requests import proxies
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Marketpercent CMC')
env = os.environ.get('env')

class Coingecko:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers)
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res

    def inser_data_to_rds(self, marketPairs, job, rds):
        """
        Mainex交易所信息 + 其他交易所信息
        """
        count_num = 0
        rank = None
        # volume_24h = None
        # volumePercent = None
        # mainex 的市占率
        mainex_volumePercent = None
        for makert in marketPairs:
            exchangeName = makert['name']
            if exchangeName == 'Mainex':
                mainex_volumePercent = round(makert['volumepercent'], 2)
        # 过滤掉未收录 mainex 的数据
        if mainex_volumePercent == None:
            logger.warning('coingecko 未收录Mainex这个交易所')
            return
        # gen rank num
        newmarketPairs_sorted = sorted(marketPairs, key=lambda x: x['volumepercent'], reverse=True)
        for makert in newmarketPairs_sorted:
            count_num += 1
            exchangeName = makert['name']
            if exchangeName == 'Mainex':
                rank = count_num
                mainex_volumePercent = makert['volume_24h']

        if rank:
            # 存入当日状态值
            name = job['name']
            symbol = job['symbol']
            spider_date = datetime.now().strftime("%Y-%m-%d")
            id = md5(f'{name}{symbol}{spider_date}'.encode()).hexdigest()
            insert_sql = f'replace into `mainex_marketpercent` values({repr(id)},{repr(name)},{repr(symbol)},{rank},{mainex_volumePercent},{mainex_volumePercent},{repr(spider_date)},{int(time.time())});'
            rds.insert(insert_sql)
        else:
            logger.warning('coingecko 未收录Mainex这个交易所')

    def get_markets(self, coin_id, job, rds, markets_list, page_num=1):
        """
        获取已上线交易所全部列表，并逻辑判断+告警
        """
        url = f'https://www.coingecko.com/en/coins/{coin_id}/markets/spot?page={page_num}'
        res = self.req(url)
        # 获取总共交易所的条数
        # dom = soupparser.fromstring(res.text)
        dom = etree.HTML(res.text.encode("ascii", "xmlcharrefreplace").decode("ascii"))
        pages_pattern = '//div[contains(text(),"Showing")]/text()'
        markets_num = dom.xpath(pages_pattern)
        if markets_num:
            content = markets_num[0].strip()
            markets_num = re.findall('of (\d+?) results',content)
            if markets_num:
                markets_num = int(markets_num[0])
            pages = ceil(markets_num/10)
            # 当进入第一页的时候才触发翻页操作
            if page_num == 1:
                for page in range(2, pages+1):
                    logger.info(f'coin_id: {coin_id} 翻页：{page}')
                    self.get_markets(coin_id, job, rds, markets_list, page_num=page)
        rows_patterns = dom.xpath('//tbody/tr')
        for row in rows_patterns:
            pair = row.xpath('./td[4]/div/a/text()')[0]
            # 剔除非usdt的交易对
            if 'USDT' not in pair:
                continue
            name = row.xpath('./td[2]/div/a/div/text()')[0]
            name = name.strip()
            volume_24h = row.xpath('./td[9]/span/text()')[0]
            volume_24h = volume_24h.replace(',', '').replace('$','')
            volume_24h = int(float(volume_24h))
            try:
                volumepercent = row.xpath('./td[10]/text()')[0].strip()
                volumepercent = volumepercent.replace('%', '')
                volumepercent = float(volumepercent)
            except:
                volumepercent = 0
            data = {
                'name':name,
                'volume_24h': volume_24h,
                'volumepercent': volumepercent
            }
            markets_list.append(data)

    def match_coingecko(self, keyword):
        """
        mainex上线的币与coingecko做匹配
        """
        # print(keyword)
        params = quote(keyword)
        url = f'https://www.coingecko.com/en/search_v2?query={params}&vs_currency=usd'
        res = self.req(url)
        coins = res.json().get('coins')
        if coins:
            coin_id = coins[0]['coin_id']
            id = coins[0]['id']
            return coin_id,id
        return

    def run(self, job, rds):
        """
        将cmc无法处理的任务（cmc未收录mainex作为交易所的代币）递交给coingecko处理
        """
        name = job['name']
        match_result = self.match_coingecko(name)
        if not match_result:
            logger.warning(f'{name} 无法在coingecko中搜索到')
            return
        coin_id, id = match_result
        if coin_id:
            markets_list = []
            # 将获取到的markets都加入列表（涉及到翻页）
            self.get_markets(coin_id, job, rds, markets_list)
            # insert data to rds
            self.inser_data_to_rds(markets_list, job, rds)
        else:
            logger.warning(f'代币无法在coingecko上搜索到：{job}')

