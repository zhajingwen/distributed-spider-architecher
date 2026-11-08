import requests
import time
import ccxt
import logging
import math
import gc
import queue
import os
import psutil
import signal
from datetime import datetime
from functools import wraps
from traceback import format_exc
from other_spider.cmc.bot.lark_bot import sender
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Queue
from decimal import *
from .filter_strategy.ma_and_pice_1d import Ma
from .filter_strategy.ma_1m import Ma1M
from .filter_strategy.ma_and_price_7d import Price7D

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MONITOR14')

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
        self.web_hook_api = os.getenv('LARK_WEBHOOK_CMC', '')
        self.redis_cli = redis_cli()
        self.black_key_base = 'cmc:black:binance:'
        self.pid_set_key = 'cmc:pid'
        self.exchange_url = 'https://www.binance.com/zh-CN/trade/{}?theme=dark&type=spot'
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
                        elif '响应码错误：408' in error:
                            logger.warning(f'{func.__name__} 响应码错误：408')
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
    def req(self, num=1):
        """
        q,进程间通信队列
        发起请求拿数据
        """
        url = self.base_url.format(num)
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'列表页：{res.status_code}: {url}')
        try:
            cryptoCurrencyList = res.json()['data']['cryptoCurrencyList']
        except:
            raise Exception(f'响应体异常,准备重试...：{res.text} {url}')
        self.parse(res, num)
        # pid = os.getpid()
        # self.redis_cli.sadd(self.pid_set_key,pid)

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
                    # # 限制100页 线程池100
                    # pool = mp.Pool(processes=100)
                    # results = []
                    # 第一次请求的初始cursor值
                    origin_start_num = 1
                    for i in range(int(totalCount/100)):
                        now_start_num = origin_start_num + 100*(i+1)
                        p = Process(target=self.req, args=(now_start_num,))
                        p.start()
                        # 控制并发
                        time.sleep(0.1)
                    # # 等待结果
                    # for result in results:
                    #     # 第一个result会阻塞后面的结果，导致后面都没有正常报错
                    #     try:
                    #         # 2分钟处理不完就杀掉
                    #         result.get(timeout=2*60)
                    #     except TimeoutError:
                    #         print(f'error{result}')
                    # pool.close()


    def currency_job(self, cryptoCurrency):
        """
        每个币的子线程job
        正常来讲一次列表能拉出来200条左右的数据
        """
        id = cryptoCurrency['id']
        name = cryptoCurrency['name']
        symbol = cryptoCurrency['symbol']
        slug = cryptoCurrency['slug']
        prices = cryptoCurrency['quotes']
        if not prices:
            logger.info(f'{symbol} 没有计价单位')
            return
        # USD计价的
        price = prices[-1]
        if price['name'] == 'USD':
            # float类型转str
            price_usd = str(price['price'])
            # percentChange24h = price['percentChange24h']
            # percentChange7d = price['percentChange7d']
            # percentChange30d = price['percentChange30d']
            percentChange1h = price['percentChange1h']
            volume24h = price['volume24h']
        else:
            logger.info(f'{symbol} 没有USD计价')
            return
        # 该统计结果相当不精准
        if percentChange1h < -2.5:
            logger.info(f'{symbol}1小时涨幅小于-2.5{percentChange1h}')
            return
        # 如果存在，那么就不报警
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{symbol}存在于黑名单{status}')
            return
        spider_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cmc_url = f'https://coinmarketcap.com/currencies/{slug}/'
        alert_data = {
            'spider_date': spider_date,
            'name': name,
            'symbol': symbol,
            'diff': '尚未统计，仅仅依赖30日和24小时的条件',
            # 'percentChange24h': f"{round(percentChange24h, 1)}%",
            # 'price_usd': price_usd,
            'cmc_url': cmc_url,
            # 'percentChange7d': percentChange7d,
            'id': id
        }
        # 交易市场正常
        status_m = self.markets_filter(slug, symbol, volume24h, id)
        if status_m:
            marketPair = status_m['marketPair']
            market = status_m['market']
            # 通过cmc 1D接口算均线 价格，k线相关数据并在方法内制定规则进行过滤
            data_1D = Ma(id, symbol, 'binance').ma_and_priceincreased()
            if data_1D:
                # 文本内容， 平均5m k线的长度
                content,normal_5mk_length,trend_99_amp_pricetoma_shockamp = data_1D
                # 小时数据拼接到 content上合并报警
                data_7D = Price7D(id, symbol, 'binance').run()
                if not data_7D:
                    return
                # 价格并且满足涨幅要求 且满足ccxt的相关过滤
                status_ccxt = self.ccxt_get(marketPair, market, symbol, id, normal_5mk_length)
                # 这里的status为{'ohlvc':ohlvc,'price_diff'}
                if status_ccxt:
                    # # 价格振幅是 k线平均长度的5倍 过滤
                    # if status_ccxt['shock_amp_50m'] > (normal_5mk_length*5):
                    #     value = f'{name} ccxt价格振幅大于k线平均长度的4倍{status_ccxt["shock_amp_50m"]}% {normal_5mk_length}%'
                    #     logger.info(value)
                    #     self.redis_cli.set(key, value, ex=5 * 5 * 60)
                    #     return
                    price_diff = status_ccxt['price_diff']
                    price_diff_ave = status_ccxt['price_diff_ave']
                    # 价格平均涨幅不得小于k线的平均长度的40%，否则不够强势
                    if price_diff_ave < normal_5mk_length*0.4:
                        value = f'{symbol} 价格平均涨幅小于k线的平均长度{price_diff_ave}% {normal_5mk_length}%'
                        logger.info(value)
                        return
                    # 5m price is under 99ma amp if bigger than increased of price filter
                    if trend_99_amp_pricetoma_shockamp < 0:
                        if price_diff < abs(trend_99_amp_pricetoma_shockamp):
                            value = f'{symbol} 偏离99ma（5m）幅度大于涨幅{trend_99_amp_pricetoma_shockamp}% {price_diff}%'
                            logger.info(value)
                            return
                    # etc是否上涨，如果上涨返回最近1m，5m的涨幅
                    eth_or_btc_status = self.get_ETH_and_btc()
                    if not eth_or_btc_status:
                        value = f'{symbol} eth 或者 btc 最近2小时内没涨'
                        logger.info(value)
                        return
                    head_coin_1m_incread,head_coin_5m_incread = eth_or_btc_status
                    content += data_7D
                    # 报警
                    alert_data['diff'] = price_diff
                    alert_data['diff_time'] = status_ccxt['diff_time']
                    # alert_data['volume'] = status_ccxt['volume']
                    alert_data['price_usd'] = self.delete_extra_zero(status_ccxt['price_usd'])
                    # marketPair
                    alert_data['url'] = self.exchange_url.format(status_ccxt['marketPair'])
                    # 偏离幅度，99单位1分钟粒度均线
                    # alert_data['on_high_amp'] = status_ccxt['on_high_amp']
                    # 最近10分钟价格的振幅情况
                    # alert_data['amplitude_10m'] = status_ccxt['amplitude_10m']
                    # cmc 1D 数据规则计算得到的值
                    alert_data['1Dvalues'] = content
                    alert_data['amplitude_1mx50'] = status_ccxt['shock_amp_50m']
                    alert_data['volume'] = status_ccxt['volume']
                    alert_data['headcoin'] = f"1m: {head_coin_1m_incread} 5m: {head_coin_5m_incread}"
                    self.alert(alert_data)

    @retry()
    def markets_filter(self, slug, name, volume24, id):
        """
        调用该币支持的交易所的接口，得到交易所列表数据
        使其满足以下策略：
        - 查询支持哪些交易所，小于10个滤掉，交易所之间行情价差异较大滤掉，
        主流交易所（交易量占比考前的）价差较大的滤掉，说明都没人愿意套利了
        挑出以usdt计价的，成交量超过百分之十的  几个交易所价格之间进行比较，
        查看价格差值，如果超过阈值那么久过滤
        """
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced'
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{name}: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'状态码异常 {res.status_code}')
        try:
            # 交易所列表策略+价格涨幅策略
            status = self.markets_filter_parse(res, name, volume24, id)
            return status
        except:
            logger.error(f'{name} {format_exc()}')
            logger.error(f'{name} 交易市场解析异常')
            return

    def markets_filter_parse(self, res, name, volume24, id):
        """
        判断交易所列表是否满足要求
        判断价格涨幅是否满足要求
        判断涨速统计区间的前30分钟是否涨过
        """
        # redis 黑名单key
        key = self.black_key_base + str(id)
        data = res.json()['data']
        marketPairs = data.get('marketPairs')
        if not marketPairs:
            return
        prices = []
        # 所有交易所名字清单
        # m_names = []
        huobi_volume = None
        binance_volume = None
        # 存放火币或者币安的交易对
        marketPairs_h_b = {}
        # 筛选交易量大于2%的
        for m in marketPairs:
            # 交易对
            marketPair = m['marketPair']
            exchangeSlug = m['exchangeSlug']
            # m_names.append(exchangeSlug)
            quoteSymbol = m['quoteSymbol']
            # 筛选用usdt 或者BUSD计价的
            if quoteSymbol in ['USDT']:
                # volumeUsd = m['volumeUsd']
                # percent = (volumeUsd / volume24) * 100
                # if percent > 2:
                # # 币安或火币得有一个交易所的成交量大于2%
                # if exchangeSlug == 'huobi':
                #     huobi_volume = True
                #     marketPairs_h_b['huobi'] = marketPair
                if exchangeSlug == 'binance':
                    binance_volume = True
                    marketPairs_h_b['binance'] = marketPair
                    prices.append(m['price'])
        if not prices:
            logger.info(f'{name}所有USDT交易市场都没有超过2%的交易量')
            value = f'{int(time.time())}{name}所有USDT交易市场都没有超过2%的交易量'
            self.redis_cli.set(key, value, ex=24 * 60 * 60)
            return
        # 用USDT的，并且成交量大于2%的，交易所总量必须大于0家
        # 此策略用于排除那些边缘性的币种
        if len(prices) < 1:
            logger.info(f'{name} 无交易量大于2%的USDT交易所')
            value = f'{int(time.time())}{name}无交易量大于2%的USDT交易所'
            self.redis_cli.set(key, value, ex=24 * 60 * 60)
            return
        # 最大价格与最小价格如果差值大于一定的幅度，就滤掉
        margin = (max(prices) - min(prices)) / min(prices)
        if margin > 1:
            logger.info(f'{name} 交易所价差大于100%了')
            value = f'{int(time.time())}{name}交易所价差大于100%'
            self.redis_cli.set(key, value, ex=24 * 60 * 60)
            return

        if binance_volume:
            market = 'binance'
            marketPair = marketPairs_h_b[market]
            res_format = {
                'marketPair':marketPair,
                'market': market,
                'name': name,
                'id': id,
            }
            return res_format
        else:
            logger.info('binance cannot satisfy volume 2%')
            value = f'{int(time.time())}{name}binance cannot satisfy volume 2%'
            self.redis_cli.set(key, value, ex=24 * 60 * 60)
            return

    @retry()
    def ccxt_get(self, marketPair, market, name, id, normal_5mk_length_cmc):
        """
        通过ccxt请求交易所接口，获取最近100分钟的价格，颗粒度1分钟
        判断行情最近几分钟是否满足涨幅要求
        最后一个元素是最近日期的
        """
        # key = self.black_key_base + str(id)
        exchange = getattr(ccxt, market)({'proxies':proxies})
        # exchange.load_markets()
        ohlcv = exchange.fetch_ohlcv(marketPair, limit=1000)
        # 可能是空列表的情况
        if not ohlcv:
            return
        price_1m_status = Ma1M(ohlcv, name, id, 'binance', normal_5mk_length_cmc).pass_verify()
        if not price_1m_status:
            return
        pass_status_1m, price_diff_ave, price_diff, diff_time, now_price,volume = price_1m_status
        logger.info(f'{name} {diff_time}分钟涨幅 {price_diff}')
        data = {
            'price_diff_ave': price_diff_ave,
            'price_diff': price_diff,
            'diff_time': int(diff_time),
            'price_usd':now_price,
            'marketPair': marketPair.replace('/','_'),
            'shock_amp_50m':pass_status_1m,
            'volume':volume
            # 'on_high_amp':on_high_amp,
            # 'amplitude_10m':amplitude_10m
        }
        return data

    @retry()
    def get_ETH_and_btc(self):
        """
        判断BTC或者ETH涨了没，最近2小时涨了那么通过，否则过滤
        通过返回 True
        """
        exchange = getattr(ccxt, 'binance')({'proxies':proxies})
        # exchange.load_markets()
        marketpairs = ['BTC/USDT','ETH/USDT']
        # increased_status = False
        # btc_1m_increased = None
        # btc_5m_increased = None
        # eth_1m_increased = None
        # eth_5m_increased = None
        for m in marketpairs:
            # 获取最近两小时的数据
            ohlcv = exchange.fetch_ohlcv(m, limit=120)
            # 可能是空列表的情况
            if not ohlcv:
                raise Exception(f'{m} have no data')
            now_price = ohlcv[-1][4]
            hours_2ago = ohlcv[0][4]
            price_increased = now_price - hours_2ago
            if price_increased > 0:
                # increased_status = True
                m1_increased = ((ohlcv[-1][4] - ohlcv[-1][1])/ohlcv[-1][1])*100
                m5_increased = ((ohlcv[-1][4] - ohlcv[-5][4]) / ohlcv[-5][4]) * 100
                return m1_increased,m5_increased
                # eth_1m_increased = ((ohlcv[-1][4] - ohlcv[-1][1]) / ohlcv[-1][1]) * 100
        # if increased_status:
        #     btc_1m_increased = ohlcv[-1][4]
        return False

    def alert(self, json_data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        时间：{json_data['spider_date']}

        Token Name：{json_data['name']}

        Token Symbol：{json_data['symbol']}

        {json_data['diff_time']}min 上涨幅度：{round(json_data['diff'],2)}%

        Token Price：${json_data['price_usd']}

        binance链接：{json_data['url']}

        ccxt 1m 50单位加权振幅：{json_data['amplitude_1mx50']}
        
        cmc 1D 统计相关数据：{json_data['1Dvalues']}
        
        成交量：{json_data['volume']}
        
        headcoin：{json_data['headcoin']}
        """
        id = json_data['id']
        # 如果存在，那么就不报警 由于高并发可能导致重复报警，redis去重失效的情况，需要进行二次验证
        key = self.black_key_base + str(id)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'{json_data["name"]}存在于黑名单{status}')
            return
        while True:
            try:
                sender(msg, self.web_hook_api)
                # 设置过期时间0.5h内报过警的就不要报了
                key = self.black_key_base + str(id)
                value = '半小时内已经告警过了'
                self.redis_cli.set(key, value, ex=30 * 60)
                break
            except:
                logger.error(f'{json_data["name"]} 发送异常')
                logger.error(f'{json_data["name"]} {format_exc()}')
                logger.error(f'{json_data["name"]} 重试...')
                time.sleep(10)

    def delete_extra_zero(self, n):
        """
        将价格转换成符合人类观看的类型
        return: str
        """
        if n < 1 and 'e' in str(n):
            x = str(math.exp(n)).replace('1.', '0.')
            return x
        return n

    def kill_child_processes(self, main_pid):
        for process in psutil.process_iter():
            try:
                # 获取进程信息
                process_info = process.as_dict(attrs=['pid', 'cmdline'])
                pid = process_info['pid']
                cmdline = process_info['cmdline']
                if 'cmc.m14' in cmdline:
                    if psutil.pid_exists(pid):
                        # 杀死未自动释放的子进程
                        if process.ppid() == main_pid:
                            process.terminate()
                            logger.info(f'杀死子进程 {pid} {cmdline}')
                        else:
                            if pid != main_pid:
                                process.terminate()
                                logger.info(f'杀死非主进程创建的子进程 {pid} {cmdline}')
                # # psutil会缓存已经关闭的子进程 进程ID只要不是程序启动的时候的ID全部关闭
                # if process.pid != main_pid and process.status() == psutil.STATUS_RUNNING:
                # # if process.ppid() == main_pid:
                #     process.terminate()
                #     logger.info(f'杀死 {process.pid}')
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def run(self):
        main_pid = os.getpid()
        num = 0
        # 30s钟跑一次
        while True:
            num += 1
            logger.info(f'循环监控：{num}')
            self.req()
            time.sleep(30)
            # # 手动垃圾回收
            # gc.collect()
            # 杀死30s前创建的所有子进程
            self.kill_child_processes(main_pid)
