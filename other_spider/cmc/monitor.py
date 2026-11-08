import requests
import time
import logging
from datetime import datetime
from functools import wraps
from traceback import format_exc
from utils.rds import DataUtils
from other_spider.cmc.bot.lark_bot import sender
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
# from other_spider.cmc.bot.tg_bot import TGbot


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MONITOR')


class Spider:
    def __init__(self):
        """
        初步的过滤条件全部都在请求中参数中过滤了
        """
        self.base_url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?' \
                   'start={}&limit=100&sortBy=market_cap&sortType=desc&convert=USD,BTC,' \
                   'ETH&cryptoType=all&tagType=all&audited=false&aux=ath,atl,high24h,' \
                   'low24h,num_market_pairs,cmc_rank,date_added,max_supply,' \
                   'circulating_supply,total_supply,volume_7d,volume_30d,self_reported_circulating_supply,' \
                   'self_reported_market_cap&volume24hRange=500000~&marketCapRange=1000000~'

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
        self.db = DataUtils('spider')
        self.pagenum = 1
        self.table = 'cmc_price_alert'
        self.redis_cli = redis_cli()
        self.black_list_key = 'cmc:black_list'
        # 接口挂了
        self.out_partment_api = 'http://dev.bitkeep.app:8897/st/tgRobotTopic'
        self.deduplication_key_base = 'cmc:deduplication'

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
    def req(self, num=1):
        """
        发起请求拿数据
        """
        url = self.base_url.format(num)
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{res.status_code}: {url}')
        self.parse(res)

    def parse(self, response):
        """
        解析数据
        读写数据库，计算涨幅
        调用报警模块
        """
        if response.status_code != 200:
            logger.info(f'列表页状态码异常：{response.status_code}')
            raise
        else:
            time_stamp = int(time.time())
            cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
            totalCount = response.json()['data']['totalCount']
            totalCount = int(totalCount)
            logger.info(f'一共{totalCount}个数据')
            for cryptoCurrency in cryptoCurrencyList:
                id = cryptoCurrency['id']
                name = cryptoCurrency['name']
                symbol = cryptoCurrency['symbol']
                slug = cryptoCurrency['slug']
                prices = cryptoCurrency['quotes']
                price_usd = None
                percentChange1h = None
                for price in prices:
                    if price['name'] == 'USD':
                        # float类型
                        price_usd = str(price['price'])
                        percentChange1h = price['percentChange1h']
                if not price_usd:
                    logger.error(f'无法解析价格：{prices}')
                    continue
                # 过滤不满足一小时条件的币
                if not percentChange1h:
                    logger.info(f'{name} no get 1 hour increase data')
                    continue
                if percentChange1h < 5:
                    logger.info(f'{name} 1 hour increase less than 5%')
                    continue
                logger.info(f'一小时涨幅：{name} {percentChange1h}')
                spider_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cmc_url = f'https://coinmarketcap.com/currencies/{slug}/'
                alert_data = {
                    'spider_date': spider_date,
                    'name': name,
                    'symbol': symbol,
                    'percentChange1h': f"{round(percentChange1h, 1)}%",
                    'price_usd': price_usd,
                    'cmc_url': cmc_url,
                    'slug':slug
                }
                status = self.req24h_toget_15mprice_increase(id,price_usd,name,alert_data)
                if status:
                    # 判断是否在黑名单里面
                    exsist_sta = self.redis_cli.sismember(self.black_list_key,name)
                    if exsist_sta:
                        logger.warning(f'{name} 黑名单不报警')
                    else:
                        # ignore the yellow warning
                        self.alert(status)
                        # self.post_to_out_partment(status)
            self.pagenum += 100
            if self.pagenum < totalCount:
                logger.info(f'当前翻页的起始值 {self.pagenum}')
                self.req(self.pagenum)
            else:
                # 当前的请求翻页结束的时候初始化该值
                self.pagenum = 1
                logger.info('翻页结束，初始化翻页计数')

    def post_to_out_partment(self, data):
        """
        将数据推送到其他部门
        """
        r = requests.post(self.out_partment_api, json=data)
        logger.info(f'requested {self.out_partment_api}')
        logger.info(f'data pushed success {r.text}')

    @retry()
    def req24h_toget_15mprice_increase(self, id, price_usd, name, alert_data):
        """
        通过24小时价格接口拿到15分钟之前的数据
        """
        price_usd = float(price_usd)
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart?id={id}&range=1D'
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{name} {res.status_code}: {url}')
        if res.status_code != 200:
            raise Exception(f'1D状态码错误：{name} {res.status_code}')
        try:
            res.json()
        except:
            logger.warning(f'{name}日线json()错误 {res.text}：{url}')
            raise Exception('res json 错误')
        try:
            res.json()['data']['points']
        except:
            logger.warning(f'{name}数据体异常 {res.text}：{url}')
            raise Exception('res points 错误')
        # judging the increase in 15m if ok return ori_data modified esle return False
        new_data_status = self.parse_24(res, price_usd, name, alert_data)
        return new_data_status

    def parse_24(self, response, price_usd, name, alert_data):
        """
        judging whether the increase in 15 minutes is greater than 10%
        数据是5分钟粒度的
        成交量在v中的1号元素，价格在0号元素
        从后往前数第三个时间点就符合15分钟（其实是大于10小于等于15的概念）
        """
        now_time = int(time.time())
        # 时间价格列表，0号元素的日期是1月前的  其中v代表开盘价，v一定存在，c代表收盘价，c不一定存在
        points = response.json()['data']['points']
        # 存放所有价格，打算剔除最高价和最低价
        # prices = []
        price_values = list(points.values())
        # 15分钟前的价格
        price_15mago = price_values[-3]['v'][0]
        price_diff = price_usd - price_15mago
        # 15分钟涨幅大于10%
        if (price_diff/price_15mago)*100 > 10:
            # 当前的24小时成交量
            vol_24_now = price_values[-1]['v'][1]
            # 24h before that timepoint vol24h
            vol_24_24hbefore = price_values[0]['v'][1]
            vol_diff = vol_24_now - vol_24_24hbefore
            # format the voldiff
            vol_diff_format = f'{round((vol_diff/vol_24_24hbefore)*100,2)}%'
            price_increase_format = f'{round((price_diff/price_15mago)*100,2)}%'
            alert_data['vol_diff_format'] = vol_diff_format
            alert_data['price_increase_format'] = price_increase_format
            alert_data['vol_24h'] = f'${round(vol_24_now,2)}'
            return alert_data
        else:
            logger.info(f'{name}15分钟涨幅小于10%')
            return False

    def alert(self, json_data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        时间：{json_data['spider_date']}

        Token Name：{json_data['name']}

        Token Symbol：{json_data['symbol']}

        15min 上涨幅度：{json_data['price_increase_format']}

        1h上涨幅度：{json_data['percentChange1h']}

        Token Price：${json_data['price_usd']}
        
        24小时交易量涨幅：{json_data['vol_diff_format']}

        24小时交易量：{json_data['vol_24h']}

        CMC链接：{json_data['cmc_url']}
        """
        while True:
            try:
                # 1小时内进行告警去重
                key = self.deduplication_key_base + f':{json_data["slug"]}'
                status = self.redis_cli.get(key)
                if not status:
                    sender(msg)
                    # TGbot().send_full(json_data)
                    # 1小时过期
                    self.redis_cli.set(key, int(time.time()), ex=1 * 60 * 60)
                break
            except:
                logger.error('发送异常')
                logger.info(format_exc())
                logger.error('重试...')
                time.sleep(10)

    def run(self):
        # 5分钟跑一次
        while True:
            self.req()
            time.sleep(5 * 60)

