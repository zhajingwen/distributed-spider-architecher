import time
from curl_cffi import requests
import logging
from retry import retry
import os
from hashlib import md5
from datetime import datetime,date,timedelta
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from .coingecko_marketpercent import Coingecko
from .alert_filter import Alert
from .utils.refresh_data_to_rds import RDS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Marketpercent CMC')
env = os.environ.get('env')

class Cmc:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_cli = redis_cli()
        self.alert = Alert()
        # 告警去重
        self.base_key = 'mainexmarketpercent:filter:{}'

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers, impersonate="chrome101")
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies, impersonate="chrome101")
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code} {url}')
        return res.json()

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

    def after_gate(self, marketPairs, job_content, job, marketpercent, slug):
        """
        市占率在Gate之后的
        """
        exchangeNames = []
        for i in marketPairs:
            exchangeName = i['exchangeName']
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
                    content = 'Mainex数据：\n' + job_content + marketpercent
                    url = f'https://coinmarketcap.com/currencies/{slug}/#Markets'
                    content += url
                    self.alert.alert(content, job['symbol'], 'aftergate')
                    return True
        return

    def marketpercent_info(self, marketPairs, job, rds):
        """
        排行名次，交易所名称，交易量，交易量市占率，交易量变化，市占率变化，
        """
        count_num = 0
        rank = None
        # volume_24h = None
        # volumePercent = None
        exchangeNames = []
        other_markets_info = ''
        # 按市占率重新算，不依据CMC的默认规则
        newmarketPairs = []
        # effectiveLiquidity list for all exchanges
        liquidity_score_list = []
        # mainex 的市占率
        mainex_volumePercent = None
        mainex_volume = None
        for makert in marketPairs:
            exchangeName = makert['exchangeName']
            quoteSymbol = makert['quoteSymbol']

            # rank 算法，交易所去重之后的rank值（比如只算USDT交易对的排名）
            if quoteSymbol != 'USDT':
                continue
            # 防止重复
            if exchangeName not in exchangeNames:
                exchangeNames.append(exchangeName)
            else:
                continue
            # 成交量存在疑问：Reserve data unavailable
            reservesAvailable = makert['reservesAvailable']
            if reservesAvailable == 0:
                continue

            # 用于计算流动性排序 rank值
            effectiveLiquidity = makert.get('effectiveLiquidity', 0)
            if effectiveLiquidity not in liquidity_score_list:
                liquidity_score_list.append(int(effectiveLiquidity))

            newmarketPairs.append(makert)
            if exchangeName == 'Mainex':
                mainex_volumePercent = round(makert['volumePercent'], 2)

        # 过滤掉未收录 mainex 的数据
        if mainex_volumePercent == None:
            return

        # 根据市占率降序排列
        newmarketPairs_sorted = sorted(newmarketPairs, key=lambda x: x['volumePercent'], reverse=True)
        # 对流动性分进行降序排列
        liquidity_score_list = sorted(liquidity_score_list, reverse=True)

        for makert in newmarketPairs_sorted:
            exchangeName = makert['exchangeName']
            volume_24h_other = makert['volumeUsd']
            volumePercent_other = round(makert['volumePercent'], 2)
            effectiveLiquidity = makert.get('effectiveLiquidity', 0)
            effectiveLiquidity = int(effectiveLiquidity)
            # 计算流动性排名
            try:
                liquidity_score_rank = liquidity_score_list.index(effectiveLiquidity)
                liquidity_score_rank += 1
            except:
                logger.error(f'流动性排名计算异常！')
                liquidity_score_rank = '计算异常'

            count_num += 1
            # 排行前10（只告警前10的交易所信息）
            if count_num < 11:
                # 其他交易所信息
                other_market_row = f'{count_num}       {exchangeName}' \
                                   f'   {self.num_transform(volume_24h_other)}' \
                                   f'   {volumePercent_other}%       {effectiveLiquidity}' \
                                   f'       {liquidity_score_rank}\n'
                other_markets_info += other_market_row
            if exchangeName == 'Mainex':
                rank = count_num
                mainex_volume_digital = volume_24h_other
                mainex_volume = self.num_transform(volume_24h_other)
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
                alert_json['市占率变化'] = f'{old_volumePercent}% > {mainex_volumePercent}%'
            marketpercent_content = ''
            for key in alert_json:
                row = f'{key}: {alert_json[key]}\n'
                marketpercent_content += row
            marketpercent_content += f'--------------------------\n\nrank' \
                                     f'  交易所  交易量    市占    流动性得分    流动性rank\n{other_markets_info}'
            return marketpercent_content
        else:
            return

    def alert_all_coins(self, job_content, job, marketpercent, slug):
        """
        所有币市占率情况推送
        """
        content = 'Mainex数据：\n' + job_content + marketpercent
        url = f'https://coinmarketcap.com/currencies/{slug}/#Markets'
        content += url
        self.alert.alert(content, job['symbol'], 'allcoins')

    def get_markets(self, slug, job, rds):
        """
        获取已上线交易所全部列表，并逻辑判断+告警
        """
        job_content = ''
        for key in job:
            row = f'{key}: {job[key]}\n'
            job_content += row
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced'
        data = self.req(url)
        data = data['data']
        try:
            numMarketPairs = data['numMarketPairs']
        except:
            logger.error(f'无法解析Response {slug} {job} {data}')
            return
        marketPairs = data.get('marketPairs')
        if len(marketPairs) > numMarketPairs:
            logger.error(f'一共上线{numMarketPairs}个交易所')
            logger.error(f'本次请求获取到{len(marketPairs)}条数据')
        if marketPairs:
            alert_content = self.marketpercent_info(marketPairs, job, rds)
            # 如果 alert_content 为空，说明CMC没有收录Mainex
            if alert_content:
                # 落后于gate报警(满足规则：在Binance or OKX 上线且落后于Gate)
                status = self.after_gate(marketPairs, job_content, job, alert_content, slug)
                if not status:
                    # 对所有的币告警
                    self.alert_all_coins(job_content, job, alert_content, slug)
            # cmc没收录，有可能coingecko收录了
            else:
                logger.warning(f'CMC未收录：{job},从Coingecko获取数据...')
                Coingecko().run(job, rds)

    def get_slug(self, all_coins, keywords):
        """
        和CMC进行匹配
        """
        origin_name = keywords[0]
        origin_symbol = keywords[1]

        slug = None
        matched = None
        # name 与 name 匹配
        for item in all_coins['values']:
            name = item[1]
            if name == origin_name:
                matched = True
                slug = item[3]
                break
        if matched:
            return slug
        else:
            # oldname 与 symbol匹配
            for item in all_coins['values']:
                symbol = item[2]
                if symbol == origin_name:
                    matched = True
                    slug = item[3]
                    break
            if matched:
                return slug
            else:
                for item in all_coins['values']:
                    symbol = item[2]
                    if symbol == origin_symbol:
                        matched = True
                        slug = item[3]
                        break
                if matched:
                    return slug
                else:
                    logger.info(f'无法和CMC完成匹配：{keywords}')
                    return

    def run(self, jobs, all_coins, rds):
        # 遍历合并后的所有任务
        for job in jobs:
            symbol = job['symbol']
            # # 补数据
            # if symbol not in ['LFT']:
            #     continue
            # 1小时内任务去重
            key = self.base_key.format(symbol)
            status = self.redis_cli.get(key)
            if status:
                logger.info(f'该任务1小时内已经处理过了：{symbol}')
                continue
            keywords = [job['name'], symbol]
            slug = self.get_slug(all_coins, keywords)
            # 如果coingecko没有收录，那么大概率不满足条件："线了币安或者OKX，且上线了gate 和 Mainex", 再往下也没有意义
            if slug:
                self.get_markets(slug, job, rds)
                time.sleep(10)
