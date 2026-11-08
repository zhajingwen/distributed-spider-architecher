import time
import csv
import requests
import logging
import json
from math import ceil
from functools import wraps
from traceback import format_exc
from threading import Thread
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies
# print(ceil(540/50))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Mainex JustOnce')

class Spider:
    def __init__(self):
        self.coin_list_base = 'https://api.coinmarketcap.com/data-api/v3/exchange/market-pairs/latest?slug=mainex&category=spot&start={}&limit=50'
        self.numMarketPairs = 513
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7",
            "cache-control": "no-cache",
            "dnt": "1",
            "origin": "https://coinmarketcap.com",
            "platform": "web",
            "referer": "https://coinmarketcap.com/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            # "x-request-id": "49fe75f8289d4bffa86643a8f0e08f50"
        }
        self.redis_cli = redis_cli()
        self.redis_key = 'mainex:justonce:coins'
        self.redis_key_cex_just_one = 'mainex:justonce:cex'
        self.sheet1 = open('sheet1.csv','w',newline='')
        self.sheet1_writer = csv.writer(self.sheet1)
        self.sheet2 = open('sheet2.csv','w',newline='')
        self.sheet2_writer = csv.writer(self.sheet2)


    def get_coin_data(self):
        coin_num = 0
        for i in range(ceil(self.numMarketPairs/50)):
            num = i*50 + 1
            url = self.coin_list_base.format(num)
            res = requests.get(url,headers=self.headers)
            logger.info(f'code: {res.status_code} {url}')
            data = res.json()['data']['marketPairs']
            for marketpair in data:
                baseCurrencySlug = marketpair['baseCurrencySlug']
                baseSymbol = marketpair['baseSymbol']
                coin_data = json.dumps({"symbol":baseSymbol,"slug":baseCurrencySlug})
                self.redis_cli.hset(self.redis_key,baseCurrencySlug,coin_data)
                coin_num += 1
                logger.info(f'{coin_num} {coin_data}')
            time.sleep(2)


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
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def markets_filter(self, slug, oridata):
        """
        调用该币支持的交易所的接口，得到交易所列表数据
        使其满足以下策略：
        - 查询支持哪些交易所，小于10个滤掉，交易所之间行情价差异较大滤掉，
        主流交易所（交易量占比考前的）价差较大的滤掉，说明都没人愿意套利了
        挑出以usdt计价的，成交量超过百分之十的  几个交易所价格之间进行比较，
        查看价格差值，如果超过阈值那么久过滤
        """
        for market_type in ['dex']:
            url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
                  f'latest?slug={slug}&start=1&limit=100&category=spot&centerType={market_type}&sort=cmc_rank_advanced'
            res = requests.get(url, headers=self.headers, proxies=proxies)
            logger.info(f'{slug}: {res.status_code} {url}')
            try:
                self.parse_market(slug,res,market_type,oridata)
            except:
                logger.error(f'无法解析：{slug} {oridata}')

    def parse_market(self, slug, res, market_type, oridata):
        data = res.json()['data']
        marketPairs = data['marketPairs']
        # prices = []
        if market_type == 'cex':
            if len(marketPairs) == 1:
                self.redis_cli.hset(self.redis_key_cex_just_one,slug,oridata)
                logger.info(f'唯一：{slug} {oridata}')
        else:
            if len(marketPairs) == 0:
                logger.info('just mainex')
                row = [json.loads(oridata)['symbol']]
                self.sheet1_writer.writerow(row)
            else:
                row = [json.loads(oridata)['symbol']]
                for m in marketPairs:
                    exchangeName = m['exchangeName']
                    row.append(exchangeName)
                self.sheet2_writer.writerow(row)





    def run(self):
        coins = self.redis_cli.hgetall(self.redis_key_cex_just_one)
        for slug in coins:
            value = coins[slug]
            self.markets_filter(slug,value)
        self.sheet1.close()
        self.sheet2.close()
            # t = Thread(target=self.markets_filter,args=(slug,value,))
            # t.start()
            # value = json.loads(value)
            # symbol = value['symbol']

        # self.redis_cli.sadd()
    def check(self):
        coins = self.redis_cli.hgetall(self.redis_key)
        coins_cmc = []
        for slug in coins:
            value = coins[slug]
            # print(value)
            symbol = json.loads(value)['symbol']
            coins_cmc.append(symbol)

        coins_mainex = self.redis_cli.hgetall('mainex:marketpairs')
        for c in coins_mainex:
            c = c.split('/')[0]
            if c not in coins_cmc:
                print(c)

    def genurl(self):
        key = 'mainex:justonce:cex'
        coins = self.redis_cli.hgetall(key)
        base = 'https://coinmarketcap.com/currencies/{}'
        for slug in coins:
            value = coins[slug]
            # print(value)
            symbol = json.loads(value)['symbol']
            url = base.format(slug)
            content = f'{symbol}  {url}'
            print(content)
            # coins_cmc.append(symbol)


