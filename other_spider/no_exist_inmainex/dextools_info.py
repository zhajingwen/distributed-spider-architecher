import requests
import logging
import json
import time
from retry import retry
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Dextools Spider')

class Dextools:
    """
    dextools爬虫
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.dextools_search_url = 'https://www.dextools.io/shared/search/pair?query={}'
        # 传入pairaddres 和chain
        # self.locks_data_url = 'https://www.dextools.io/shared/data/pair?address={}&chain={}&audit=true&locks=true'
        self.cookies_store = 'bk-early:cookies'
        # 合约风险检测
        # self.goplus_risk = GoplusRisk()
        # self.jobs_Key =
        self.job_key = f'noexistinmainex:jobs'
        self.result_key = 'noexistinmainex:result'


    @retry(tries=100, delay=3)
    def req(self, url):
        """
        通过搜索接口获取到代币的详情
        """
        # 获取cookie
        cookie_dict = self.get_cookie()
        headers = {
            "Referer": "https://www.dextools.io/app/cn/pairs",
            'User-Agent': cookie_dict['ua'],
        }
        proxies = {
            'http': cookie_dict['proxy'],
            'https': cookie_dict['proxy']
        }
        logger.info(f'request: {url}')
        if 'cf' in cookie_dict:
            cookies = cookie_dict['cf']
            res = requests.get(url, headers=headers, proxies=proxies, cookies=cookies)
        else:
            res = requests.get(url, headers=headers, proxies=proxies)
        logger.info(f'response code: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code} {url}')
        else:
            # 真能获取到数据再把cookie放回去
            self.redis_cli.sadd(self.cookies_store, json.dumps(cookie_dict))
        return res

    def get_cookie(self):
        """
        从数据库拿取有效的cookie，如果没有就hold
        """
        while True:
            cookie_json = self.redis_cli.spop(self.cookies_store)
            if not cookie_json:
                logger.warning('当前没有可调用的cookies,等待...')
                time.sleep(5)
                continue
            cookie_dict = json.loads(cookie_json)
            # cookie超过有效期，那么就重新获取
            timestamp = cookie_dict['timestamp']
            if (int(time.time()) - timestamp) > 30 * 60:
                pass
            else:
                return cookie_dict

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

    def risk(self, data):
        """
        输出代币风险
        return: str 合约风险信息
        """
        risk_content = []
        buy_tax = data['buy_tax']
        max = buy_tax['max']
        if max != 0:
            risk_content.append(f'买入税率最大值：{max}')
        min = buy_tax['min']
        if min != 0:
            risk_content.append(f'买入税率最小值：{min}')
        is_blacklisted = data['is_blacklisted']
        if is_blacklisted != 'no':
            risk_content.append('存在黑名单机制')
        is_honeypot = data['is_honeypot']
        if is_honeypot != 'no':
            risk_content.append('貔貅盘')
        is_mintable = data['is_mintable']
        if is_mintable != 'no':
            risk_content.append('可增发')
        is_open_source = data['is_open_source']
        if is_open_source != 'yes':
            risk_content.append('未开源')
        is_potentially_scam = data['is_potentially_scam']
        if is_potentially_scam != 'no':
            risk_content.append('存在 potentially_scam')
        is_proxy = data['is_proxy']
        if is_proxy != 'no':
            risk_content.append('存在 代理')
        sell_tax = data['sell_tax']
        max = sell_tax['max']
        if max != 0:
            risk_content.append(f'卖出税率最大值：{max}')
        min = sell_tax['min']
        if min != 0:
            risk_content.append(f'卖出税率最小值：{min}')
        slippage_modifiable = data['slippage_modifiable']
        if slippage_modifiable != 'no':
            risk_content.append('滑点可修改')
        transfer_pausable = data['transfer_pausable']
        if transfer_pausable != 'no':
            risk_content.append('交易可暂停')
        if risk_content:
            return ','.join(risk_content)
        else:
            return

    def get_detail_data(self, job):
        """
        从dextools获取代币详情
        """
        address = job.get('address')
        url = self.dextools_search_url.format(address)
        res = self.req(url)
        data = res.json()['results']
        if not data:
            self.redis_cli.sadd(self.result_key, json.dumps(job))
            return

        data = data[0]
        try:
            # 链上交易量
            dex_volume = int(data['volume'])
            swaps = data['swaps']
            # cex交易量
            cex_volume = int(job['volume24h'] - dex_volume)
        except:
            # 链上交易量
            dex_volume = ''
            swaps = ''
            # cex交易量
            cex_volume = ''
        # 流动池
        LIQUIDITY = data['metrics']['liquidity']

        job['dex_volume'] = dex_volume
        job['swaps'] = swaps
        job['cex_volume'] = cex_volume
        job['LIQUIDITY'] = LIQUIDITY

        job['contract risk'] = ''
        job['holders'] = ''

        token = data.get('token')
        if token:
            token_metrics = token.get('metrics')
            audit = token.get('audit')
            if audit:
                # codeVerified = audit['codeVerified']
                risk_dict = audit.get('dextools')
                if risk_dict:
                    risk_content = self.risk(risk_dict)
                    if risk_content:
                        job['contract risk'] = risk_content
                    if token_metrics:
                        holders = token_metrics.get('holders')
                        job['holders'] = holders
        self.redis_cli.sadd(self.result_key, json.dumps(job))
        logger.info(f'额外数据获取成功{job}')

    def run(self):
        """
        处理输入的消息是合约地址
        """
        while True:
            job = self.redis_cli.spop(self.job_key)
            if not job:
                logger.info('任务已全部消费完')
                break
            logger.info(f'开始处理任务：{job}')
            if not isinstance(job, dict):
                job = json.loads(job)
            address =job.get('address')
            if address:
                if len(address) == 42:
                    # 补全数据塞入redis
                    self.get_detail_data(job)
                else:
                    self.redis_cli.sadd(self.result_key, json.dumps(job))
            else:
                self.redis_cli.sadd(self.result_key, json.dumps(job))
