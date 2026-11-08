import requests
import logging
import queue
from traceback import format_exc
from utils.proxy_requests import proxies
from concurrent.futures import ThreadPoolExecutor
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MONITOR3')

class MyThreadPoolExecutor(ThreadPoolExecutor):
    """
    重写线程池修改队列数
    """
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers, thread_name_prefix)
        # 队列大小为最大线程数的1倍
        self._work_queue = queue.Queue(self._max_workers * 1)


class Spider:

    def __init__(self):
        # 满足1和2的过滤条件
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
        # self.web_hook_api = '<LARK_WEBHOOK_FEISHU_ALERT>'
        # self.web_hook_api = '<LARK_WEBHOOK_ALERT>'
        # self.web_hook_api = '<LARK_WEBHOOK_CMC>'
        # self.redis_cli = redis_cli()
        # self.black_key_base = 'cmc:black:binance:'
        self.pid_set_key = 'cmc:pid'
        # self.exchange_url = 'https://www.binance.com/zh-CN/trade/{}?theme=dark&type=spot'
        # 线程数
        self.excutor = MyThreadPoolExecutor(max_workers=3)

    def executor_callback(self, worker):
        """
        线程池回调函数
        """
        # logger.info("called worker callback function")
        worker_exception = worker.exception()
        # worker.
        if worker_exception:
            # logger.exception("Worker return exception: {}".format(worker_exception))
            raise worker_exception

    @retry()
    def req(self, num=1):
        """
        q,进程间通信队列
        发起请求拿数据
        """
        url = self.base_url.format(num)
        logger.info(f'GET LISTPAGE {num}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'Response LISTPAGE {res.status_code} {num}')
        # logger.info(f'列表页：{res.status_code}: {url}')
        try:
            cryptoCurrencyList = res.json()['data']['cryptoCurrencyList']
        except:
            raise Exception(f'响应体异常,准备重试...：{res.text} {url}')
        self.parse(res, num)

    def parse(self, response, num):
        """
        解析数据
        读写数据库，计算涨幅
        调用报警模块
        """
        if response.status_code != 200:
            logger.info(f'列表页状态码异常：{response.status_code}')
            raise Exception(f'response status code error: {response.status_code}')
        else:
            cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
            totalCount = response.json()['data']['totalCount']
            totalCount = int(totalCount)
            for cryptoCurrency in cryptoCurrencyList:
                # 如果条件url筛选出来的URL有100个，那么并发就是100个，上限是100，有多少算多少；
                # t = Thread(target=self.currency_job, args=(cryptoCurrency,))
                # t.start()
                self.excutor.submit(self.currency_job, cryptoCurrency).add_done_callback(self.executor_callback)

            # 翻页
            # 请求首页的时候才进入翻页的逻辑，避免无限递归
            if num == 1:
                logger.info(f'一共{totalCount}个数据')
                # 大于100条才需要翻页
                if totalCount > 100:
                    # 第一次请求的初始cursor值
                    origin_start_num = 1
                    for i in range(int(totalCount / 100)):
                        # 翻页参数
                        now_start_num = origin_start_num + 100 * (i + 1)
                        # 翻页
                        self.req(now_start_num)

    def currency_job(self, cryptoCurrency):
        """
        每个币的子线程job
        正常来讲一次列表能拉出来200条左右的数据
        """
        # id = cryptoCurrency['id']
        # name = cryptoCurrency['name']
        symbol = cryptoCurrency['symbol']
        slug = cryptoCurrency['slug']
        prices = cryptoCurrency['quotes']
        if not prices:
            logger.info(f'{symbol} 没有计价单位')
            return
        self.markets_filter(slug, symbol)

    @retry()
    def markets_filter(self, slug, symbol):
        """
        调用该币支持的交易所的接口，得到交易所列表数据
        使其满足以下策略：
        - 查询支持哪些交易所，小于10个滤掉，交易所之间行情价差异较大滤掉，
        主流交易所（交易量占比考前的）价差较大的滤掉，说明都没人愿意套利了
        挑出以usdt计价的，成交量超过百分之十的  几个交易所价格之间进行比较，
        查看价格差值，如果超过阈值那么久过滤
        """
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=10&category=spot&centerType=cex&sort=cmc_rank_advanced'
        res = requests.get(url, headers=self.headers, proxies=proxies)
        # logger.info(f'{symbol}: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'状态码异常 {res.status_code}')
        try:
            # 交易所列表策略+价格涨幅策略
            status = self.markets_filter_parse(res, symbol)
            return status
        except:
            logger.error(f'{symbol} {format_exc()}')
            logger.error(f'{symbol} 交易市场解析异常')
            return

    def markets_filter_parse(self, res, symbol):
        """
        判断交易所列表是否满足要求
        判断价格涨幅是否满足要求
        判断涨速统计区间的前30分钟是否涨过
        """
        data = res.json()['data']
        marketPairs = data.get('marketPairs')
        name = data.get('name')
        # symbol = data['symbol']
        if not marketPairs:
            logger.info(f'{symbol} 无任何cex')
            return
        if len(marketPairs) == 1:
            exchangeSlug = marketPairs[0]['exchangeSlug']
            if exchangeSlug == 'mainex':
                marketUrl = marketPairs[0]['marketUrl']
                logger.info(marketUrl)
            else:
                logger.info(f'{symbol} 唯一一个交易所并不是mainex')
        else:
            black_list = ['htx', 'binance', 'bybit', 'okx', 'kraken']
            all_m = []
            alert = True
            for m in marketPairs:
                exchangeSlug = m['exchangeSlug']
                if exchangeSlug in black_list:
                    alert = False
                    all_m.append(exchangeSlug)
            if 'mainex' not in all_m:
                alert = False
            if alert:
                logger.info(f'name symbol: {name} / {symbol}')
            # logger.info(f'{symbol} cex大于1')

    def run(self):
        self.req()