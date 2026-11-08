import time
# import requests
from curl_cffi import requests
import logging
import re
import os
from math import ceil
from lxml import etree
from retry import retry
from hashlib import md5
from datetime import datetime,date,timedelta
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from urllib.parse import quote
from .alert_filter import Alert
from .utils.refresh_data_to_rds import RDS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko CMC')
env = os.environ.get('env')

class Coingecko:
    def __init__(self):
        self.headers = {
            # "referer": "User-Agent",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_cli = redis_cli()
        self.alert = Alert()

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers, impersonate="chrome101")
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies, impersonate="chrome101")
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {url}')
        return res

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

    def after_gate(self, marketPairs, job, alert_content, slug):
        """
        市占率在Gate之后的
        """
        exchangeNames = []
        for i in marketPairs:
            exchangeName = i['name']
            # 防止重复
            if exchangeName not in exchangeNames:
                exchangeNames.append(exchangeName)
        # 上线了币安或者OKX
        if 'Binance' in exchangeNames or 'OKX' in exchangeNames:
            # 上线了gate
            if 'Gate.io' in exchangeNames:
                gate_order_num = exchangeNames.index('Gate.io')
                try:
                    mainex_order_num = exchangeNames.index('Mainex')
                except:
                    logger.error(marketPairs)
                    return
                if mainex_order_num > gate_order_num:
                    url = f'https://coinmarketcap.com/currencies/{slug}/#Markets'
                    alert_content += url
                    self.alert.alert(alert_content, job['symbol'], 'aftergate')
                    return True
        return

    def alert_all_coins(self, job, alert_content, id):
        """
        所有币市占率情况推送
        """
        url = f'https://www.coingecko.com/en/coins/{id}'
        alert_content += url
        self.alert.alert(alert_content, job['symbol'], 'allcoins')

    def sorted_markets(self, marketPairs, alert_content, job, id):
        # 落后于gate报警
        status = self.after_gate(marketPairs, job, alert_content, id)
        if not status:
            # 对所有的币告警
            self.alert_all_coins(job, alert_content, id)

    def marketpercent_info(self, marketPairs, job, rds):
        """
        Mainex交易所信息 + 其他交易所信息
        """
        count_num = 0
        rank = None
        # volume_24h = None
        # volumePercent = None
        # exchangeNames = []
        other_markets_info = ''
        # 按市占率重新算，不依据CMC的默认规则
        # newmarketPairs = []
        # mainex 的市占率
        mainex_volumePercent = None
        mainex_volume = None
        for makert in marketPairs:
            exchangeName = makert['name']
            # newmarketPairs.append(makert)
            # print(exchangeName)
            if exchangeName == 'Mainex':
                mainex_volumePercent = round(makert['volumepercent'], 2)
        # print(mainex_volumePercent)
        # 过滤掉未收录 mainex 的数据
        # 过滤掉未收录 mainex 的数据
        if mainex_volumePercent == None:
            return
        newmarketPairs_sorted = sorted(marketPairs, key=lambda x: x['volumepercent'], reverse=True)
        for makert in newmarketPairs_sorted:
            volume_24h = makert['volume_24h']
            volumePercent = round(makert['volumepercent'], 2)

            count_num += 1
            exchangeName = makert['name']

            # 排行前10
            if count_num < 11:
                # 其他交易所信息
                other_market_row = f'{count_num}       {exchangeName}   {self.num_transform(volume_24h)}   {volumePercent}%\n'
                other_markets_info += other_market_row

            if exchangeName == 'Mainex':
                rank = count_num
                mainex_volume_digital = volume_24h
                mainex_volume = self.num_transform(volume_24h)
        # print(rank)
        if rank:
            alert_json = {
                'rank':rank,
                'volume_24h': mainex_volume,
                '市占率': f'{mainex_volumePercent}%'
            }
            # 存入当日状态值
            name = job['name']
            symbol = job['symbol']
            spider_date = datetime.now().strftime("%Y-%m-%d")
            id = md5(f'{name}{symbol}{spider_date}'.encode()).hexdigest()
            insert_sql = f'replace into `mainex_marketpercent` values({repr(id)},{repr(name)},{repr(symbol)},{rank},{mainex_volume_digital},{mainex_volumePercent},{repr(spider_date)},{int(time.time())});'
            # insert_sql = f'update mainex_marketpercent set volume_24h={mainex_volume_digital}, ' \
            #              f'volumePercent={mainex_volumePercent} where spider_date="{spider_date}" and symbol="{symbol}";'
            # 落库
            RDS().insert_rds(self.redis_cli, insert_sql, rds, id)
            # 获取历史数据
            yesterday = date.today() + timedelta(-1)
            spider_date_yesterday = yesterday.strftime("%Y-%m-%d")
            old_id = md5(f'{name}{symbol}{spider_date_yesterday}'.encode()).hexdigest()
            select_sql = f'select `rank`,`volume_24h`,`volumePercent` from `mainex_marketpercent` where id="{old_id}";'
            old_data = rds.select(select_sql)
            if old_data:
                old_rank = old_data[0]['rank']
                old_volume_24h = old_data[0]['volume_24h']
                old_volumePercent = old_data[0]['volumePercent']
                rank_diff = rank - old_rank
                if rank_diff < 0:
                    rank_diff = f'排名上升 {abs(rank_diff)} 名'
                elif rank_diff == 0:
                    rank_diff = '不变'
                else:
                    rank_diff = f'排名下跌 {rank_diff} 名'
                alert_json['rank变化'] = rank_diff
                if old_volume_24h == 0:
                    volume_diff = '昨日数据为0'
                else:
                    volume_diff = round(((mainex_volume_digital - old_volume_24h)/old_volume_24h)*100,2)
                    if volume_diff > 0:
                        volume_diff = f'+{volume_diff}%'
                    else:
                        volume_diff = f'{volume_diff}%'
                alert_json['volume24H变化'] = volume_diff
                alert_json['市占率24H变化'] = f'{old_volumePercent}% > {mainex_volumePercent}%'
            # mainex交易所信息
            marketpercent_content = ''
            for key in alert_json:
                row = f'{key}: {alert_json[key]}\n'
                marketpercent_content += row
            marketpercent_content += f'--------------------------\n\nrank  交易所  交易量    市占\n{other_markets_info}'
            return marketpercent_content
        else:
            return

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
            # print(markets_num)
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

    def run(self, job, rds):
        name = job['name']
        match_result = self.match_coingecko(name)
        if not match_result:
            logger.warning(f'{name} 无法在coingecko中搜索到')
            return
        coin_id, id = match_result
        if coin_id:
            markets_list = []
            # 将获取到的markets都加入列表
            self.get_markets(coin_id, job, rds, markets_list)
            # 组装告警内容
            alert_content = self.marketpercent_info(markets_list, job, rds)
            job_content = ''
            for key in job:
                # if key == 'symbol':
                #     continue
                row = f'{key}: {job[key]}\n'
                job_content += row
            if alert_content:
                alert_content = 'Mainex数据：\n' + job_content + alert_content
                self.sorted_markets(markets_list, alert_content, job, id)
            else:
                logger.warning(f'Coingecko未收录：{job}')

