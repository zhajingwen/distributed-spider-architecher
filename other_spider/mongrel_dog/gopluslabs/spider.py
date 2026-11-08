import os
import requests
import json
import time
import logging
from traceback import format_exc
from functools import wraps
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.proxy_requests import proxies
from other_spider.mongrel_dog.lark_bot import sender


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gopluslabs')

class Spider:
    def __init__(self):
        # self.chains = {'Ethereum': '1', 'Optimism': '10', 'Cronos': '25', 'BSC': '56', 'OKC': '66', 'Gnosis': '100', 'HECO': '128', 'Polygon': '137', 'Fantom': '250', 'KCC': '321', 'zkSync': '324', 'ETHW': '10001', 'FON': '201022', 'Arbitrum': '42161', 'Avalanche': '43114', 'Linea': '59140', 'Harmony': '1666600000', 'Tron': 'tron'}
        # goplus公链ID映射
        # 有可能存在任务包中的公链不在下面的dict中
        self.chains = {'ethereum': '1', 'optimism': '10', 'cronos': '25', 'bsc': '56', 'okc': '66', 'gnosis': '100', 'heco': '128', 'polygon': '137', 'fantom': '250', 'kcc': '321', 'zksync': '324', 'ethw': '10001', 'fon': '201022', 'arbitrum': '42161', 'avalanche': '43114', 'linea': '59140', 'harmony': '1666600000', 'tron': 'tron'}
        self.base_url = 'https://api.gopluslabs.io/api/v1/token_security/{}?contract_addresses={}'
        self.redis_cli = redis_cli()
        self.rds = DataUtils(db='spider')
        self.mysql_table = 'dexscreener2'
        self.black_list = 'mongrel:blacklist'
        # 合约检测记录，用于检测去重，永远只检测一次
        self.white_list = 'mongrel:whitelist'
        # hash结构，记录代币历史刷新时间戳
        self.coin_price_refresh_time = 'mongrel:coinprice:refreshtime'
        # 检查是否有需要剔除的代币（从数据库）0 表示可以获取 self.coin_price_refresh_time 的内容
        self.coins_get_status = 'mongrel:coinprice:refreshtime:datagetstatus'
        # 从数据删除数据任务
        self.deletedata_jobs = 'mongrel:deletedata:jobs_backup'
        # 列表页过来的任务列表
        self.page_list_key = 'mongrel:dexscreener:pagelist'
        self.headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
            }
        self.lark_bot_url = os.getenv('LARK_WEBHOOK_MONGREL_DOG', '')
        self.alert_filter_base = 'mongrel:alert:filter:{}'
        self.user_a_jobs = 'mongrel:user_a:jobs'

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
    def req(self, url):
        """
        发起合约检测请求
        """
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res

    def price_increased_filter(self, job):
        """
        6小时涨幅>1%，24小时涨幅>10%
        满足涨幅需求返回True
        """
        priceChange_h6 = job['priceChange']['h6']
        priceChange_h24 = job['priceChange']['h24']
        if priceChange_h6 > 1 and priceChange_h24 > 10:
            return True
        else:
            logger.info(f'不满足涨幅要求，过滤！{job}')
            return False

    def dexscreener_rule_deal(self, num):
        """
        dexscreener的一些过滤规则处理
        return：None or coinsadjust  None就跳出
        """
        job = self.redis_cli.spop(self.page_list_key)
        if not job:
            logger.info('暂无任务...')
            # 程序初始化num是1，此时不需要 sleep
            if num > 1:
                # 由于上游程序（dexscreener）每小时调度一次，因此这边理想情况下每小时才会出现一批任务，为了避免过多的日志打印，当任务消费完时设置等待时间为20M
                time.sleep(20*60)
            return
        job = json.loads(job)
        chain_name = job['chainId']
        addresss = job['baseToken']['address']
        # 存在于黑名单过滤
        if self.redis_cli.sismember(self.black_list,addresss):
            return
        # 校验公链
        if chain_name not in self.chains:
            logger.info(f'不支持的公链：{chain_name}')
            self.redis_cli.sadd(self.black_list,addresss)
            return
        # 检测是否满足涨幅需求 决定是否做报警推送
        if not self.price_increased_filter(job):
            return
        # 一小时内告警去重
        name = job['baseToken']['name']
        filter_key = self.alert_filter_base.format(name)
        # 去重
        if self.redis_cli.get(filter_key):
            return
        return job

    def goplus_rule_deal(self, job):
        """
        goplus的一些过滤规则（在dexcreener过滤之后进行）
        return：None or another_user_a_project_job  None就跳出
        """
        # 作为任务包推送到redis队列，给user_a的早期造富测试项目消费
        another_user_a_project_job = {"dexscreener": job, "goplus":None}

        chain_name = job['chainId']
        addresss = job['baseToken']['address']

        # 进行过合约检测的
        # 不管合约过没过，只要检测过，都得跳出（因为，如果过了那么一定是告警过了，如果没过，再次检测也没有意义；这里假定合约检测结果是死的）
        if self.redis_cli.sismember(self.white_list,addresss):
            return

        # 合约检测
        chain_id = self.chains[chain_name]
        url = self.base_url.format(chain_id,addresss)
        res = self.req(url)
        if not res:
            logger.info(f'请求失败：{url}')
            return
        # 合约检测记录
        self.redis_cli.sadd(self.white_list,addresss)
        data = res.json()['result']
        if not data:
            logger.info(f'无数据：{url}')
            self.redis_cli.sadd(self.black_list,addresss)
            return
        data = data[addresss.lower()]
        try:
            if self.risk_check(data):
                logger.info(f'有合约风险 {url}')
                self.redis_cli.sadd(self.black_list,addresss)
                return
            logger.info(data)
        except:
            logger.warning('存在字段缺失的情况:')
            # logger.info(format_exc())
        # 合并goplus数据
        another_user_a_project_job["goplus"] = data
        return another_user_a_project_job

    def consumer(self, num):
        """
        从redis拿任务检测是否存在风险 (dexcreener + goplus)
        """
        job = self.dexscreener_rule_deal(num)
        # 不满足dexcreener的过滤规则
        if not job:
            return

        # 不满足合约检测，过滤
        goplus_status = self.goplus_rule_deal(job)
        if not goplus_status:
            return

        # 生成需要删除数据垃圾数据的任务
        self.check_for_updates_to_gendeletejobs(job)
        # 入库
        self.insert_data(job)

        # # 告警 + 记录告警记录（为了去重）
        # format_content = self.aler_content(coinsadjust)
        # sender(format_content, self.lark_bot_url, 'dexscreener')
        # name = coinsadjust['baseToken']['name']
        # filter_key = self.alert_filter_base.format(name)
        # self.redis_cli.setex(filter_key, 60 * 60, 1)

        # 首次触发合约检测的币，会推送到user_a的任务队列
        # 这种方式有个问题，如果该程序没上线，曾经就已经触发过合约检测了，那么会被滤掉 (已经通过全部的初始化来解决这个问题了)
        another_user_a_project_job = goplus_status
        if another_user_a_project_job["goplus"]:
            logger.info(f'生成2.0任务：{another_user_a_project_job}')
            self.redis_cli.sadd(self.user_a_jobs, json.dumps(another_user_a_project_job))

    def insert_data(self, data):
        """
        入库
        """
        name = data['baseToken']['name']
        quote = f"{data['baseToken']['symbol']}/{data['quoteTokenSymbol']}"
        price = float(data['priceUsd'])
        trade_times = data['txns']['h24']['buys'] + data['txns']['h24']['sells']
        priceChange_m5 = data['priceChange']['m5']
        priceChange_h1 = data['priceChange']['h1']
        priceChange_h6 = data['priceChange']['h6']
        priceChange_h24 = data['priceChange']['h24']
        volume = int(data['volume']['h24'])
        liquidity = int(data['liquidity']['usd'])
        FDV = data['marketCap']
        sql = f'insert into {self.mysql_table} (quote,name,price,trade_times,' \
              f'volume,price_increaed_in5m,' \
              f'price_increaed_in1h,price_increaed_in6h,price_increaed_in24h,' \
              f'liquidity,FDV,update_time,spider_date) values ({repr(quote)},{repr(name)},' \
              f'{price},{trade_times},{volume},{priceChange_m5},{priceChange_h1},' \
              f'{priceChange_h6},{priceChange_h24},{liquidity},{FDV},{int(time.time())},now());'
        self.rds.insert(sql)

    def check_for_updates_to_gendeletejobs(self, data):
        """
        新增记录，剔除长时间没有更新的老记录
        """
        name = data['baseToken']['name']
        # 确保当前批次没有检查过
        status = self.redis_cli.get(self.coins_get_status)
        if not status:
            # 由于该操作比较耗时，每批次只操作一次
            allcoins_data = self.redis_cli.hgetall(self.coin_price_refresh_time)
            # 过期时间30分钟，确保当前批次只操作一次
            self.redis_cli.setex(self.coins_get_status,30*60,1)
            for coin in allcoins_data:
                last_update_time = int(allcoins_data[coin])
                # 超过1小时没有更新剔除历史记录
                if time.time()-last_update_time > 1.5*60*60:
                    # 将剔除任务添加到任务队列
                    self.redis_cli.sadd(self.deletedata_jobs,name)
        # 刷新 更新记录
        self.redis_cli.hset(self.coin_price_refresh_time, name, int(time.time()))

    def risk_check(self, data):
        """
        合约风险检测
        如果有风险返回True
        """
        owner_change_balance = data['owner_change_balance']
        # 优先级最高 并且aaron确定如果无代理风险，那么后面的字段一定不会缺失
        is_proxy = data['is_proxy']
        if is_proxy == '1':
            risk = True
            return risk
        # is_open_source = data['is_open_source']
        # is_mintable = data['is_mintable']
        # can_take_back_ownership = data['can_take_back_ownership']
        hidden_owner = data['hidden_owner']
        selfdestruct = data['selfdestruct']
        external_call = data['external_call']
        is_honeypot = data['is_honeypot']
        buy_tax = float(data.get('buy_tax',0))
        sell_tax = float(data.get('sell_tax',0))
        risk = False
        if owner_change_balance == '1':
            risk = True
        # if is_open_source == '0':
        #     risk = True

        # if is_mintable == '1':
        #     risk = True
        # if can_take_back_ownership == '1':
        #     risk = True
        if hidden_owner == '1':
            risk = True
        if selfdestruct == '1':
            risk = True
        if external_call == '1':
            risk = True
        if is_honeypot == '1':
            risk = True
        if buy_tax > 0.2:
            risk = True
        if sell_tax > 0.2:
            risk = True
        return risk

    def aler_content(self, data):
        """
        拼接告警内容
        """
        name = data['baseToken']['name']
        price = data['priceUsd']
        priceChange_h6 = data['priceChange']['h6']
        priceChange_h24 = data['priceChange']['h24']
        volume = data['volume']['h24']/1000000
        volume = round(volume, 3)
        pairAddress = data['pairAddress']
        chainId = data['chainId']
        url = f'https://dexscreener.com/{chainId}/{pairAddress}'
        marketCap = data['marketCap']
        # last_time_stamp = int(time.time()) - 1.5*60*60
        # sql = f'SELECT trade_times FROM spider.dexscreener where name={repr(name)} and update_time > {last_time_stamp};'
        # res = self.rds.select(sql)
        # if res:
        #     trade_times_old = res[0]['trade_times']
        #     trade_times = data['txns']['h24']['buys'] + data['txns']['h24']['sells']
        #     trx_1h = trade_times - trade_times_old
        # else:
        #     trx_1h = '无历史数据，无法计算'
        #
        txns = data['txns']
        trx_1h = txns['h1']['buys'] + txns['h1']['sells']
        # trx_1h = txns['h1']['buys']['sells']
        liquidity = int(data['liquidity']['usd'])
        content = f"""{name} 价格异动，目前交易情况：
        
        1、 当前价格：${price}
        2、 6小时涨幅：{priceChange_h6}%
        3、 24小时涨幅：{priceChange_h24}%
        4、 交易量：{volume} M
        5、 Dexscreener链接：{url}
        6、 市值：{marketCap}
        7、 1小时交易笔数：{trx_1h}
        8、 liquidity：{liquidity}
        """
        return content

    def run(self):
        # 启动循环的次数
        num = 0
        while True:
            num += 1
            # 防止数值过大，占用内存
            if num > 100:
                num = 2
            self.consumer(num)



