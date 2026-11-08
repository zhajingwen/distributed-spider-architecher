from curl_cffi import requests
import logging
import time
from retry import retry
from datetime import datetime
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from .get_twitter_followers import TwitterFollowers
from .security import Security

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gems Data Geted')


class FindGems:
    def __init__(self):
        self.url = 'https://multichain-api.birdeye.so/solana/gems'
        self.payload = {
            "sort_by": "view24h",
            "sort_type": "desc",
            "offset": 0,
            "limit": 50,
            "query": [],
            "export": False
        }
        self.redis_cli = redis_cli()
        self.redis_key = 'cloudflare:agentids'
        self.headers = {
            # "Agent-Id": "<BIRDEYE_AGENT_KEY>",
            "Content-Type": "application/json",
            "Origin": "https://birdeye.so",
            "Page": "find_gems",
            "Referer": "https://birdeye.so/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        self.rds = DataUtils()
        self.get_followers = TwitterFollowers()
        self.security = Security()

    @retry(tries=3, delay=10)
    def req(self):
        agent_id = self.redis_cli.spop(self.redis_key)
        logger.info(f'获取到agent-id: {agent_id}')
        headers = {
            "Agent-Id": agent_id,
            "Content-Type": "application/json",
            "Origin": "https://birdeye.so",
            "Page": "find_gems",
            "Referer": "https://birdeye.so/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        logger.info(f'Post: {agent_id}')
        res = requests.post(self.url, json=self.payload, headers=headers, impersonate="chrome101")
        logger.info(f'Response {res.status_code}: {agent_id}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        else:
            # 如果ID能获取到正常数据，再塞回redis
            self.redis_cli.sadd(self.redis_key, agent_id)
        return res.json()

    def data_to_rds(self):
        """
        解析数据 + 数据落库
        """
        spider_date = datetime.now().strftime("%Y-%m-%d")
        spider_time = int(time.time())
        data = self.req()
        items = data['data']['items']
        for item in items:
            id = item['address']
            symbol = item['symbol']
            name = item['name']
            # 单位% 类型float
            priceChange30mPercent = item['priceChange30mPercent']
            priceChange30mPercent = round(priceChange30mPercent, 2)
            priceChange1hPercent = item['priceChange1hPercent']
            priceChange1hPercent = round(priceChange1hPercent, 2)
            priceChange2hPercent = item['priceChange2hPercent']
            priceChange2hPercent = round(priceChange2hPercent, 2)
            priceChange24hPercent = item['priceChange24hPercent']
            priceChange24hPercent = round(priceChange24hPercent, 2)
            liquidity = item['liquidity']
            liquidity = round(liquidity, 2)
            # 单位USD
            vol_24h = int(item['v24hUSD'])

            trade24h = item['trade24h']
            holders = item['holder']
            fdmc = int(item['supply']*item['price'])
            # 查看记录存不存在
            select_sql = f'select * from birdeye_gems where address={repr(id)};'
            exsist_status = self.rds.select(select_sql)
            # 不存在则insert （且需要请求twitter数据，合约检测数据）
            if not exsist_status:
                sql_base = 'insert into birdeye_gems(`address`,`symbol`,`name`,`m30`,`h1`,`h2`,`h24`,`TVL`,`vol_24h`,' \
                           '`trades_24h`,`holders`,`FDMC`,`Twitter_followers`,`security`,`spider_date`,`spider_time`) values{};'
                Twitter_followers = self.get_followers.followers(id)
                security = self.security.get_security_info(id)
                sql_value = f'({repr(id)},{repr(symbol)},{repr(name)},{priceChange30mPercent},' \
                            f'{priceChange1hPercent},{priceChange2hPercent},{priceChange24hPercent},' \
                            f'{liquidity},{vol_24h},{trade24h},{holders},{fdmc},{repr(Twitter_followers)},' \
                            f'{repr(security)},{repr(spider_date)},{spider_time})'
                insert_sql = sql_base.format(sql_value)
                self.rds.insert(insert_sql)
            else:
                update_sql = f'update birdeye_gems set `m30`={priceChange30mPercent},`h1`={priceChange1hPercent},' \
                             f'`h2`={priceChange2hPercent},`h24`={priceChange24hPercent},`TVL`={liquidity},' \
                             f'`vol_24h`={vol_24h},`trades_24h`={trade24h},`holders`={holders},' \
                             f'`FDMC`={fdmc},`spider_date`={repr(spider_date)},`spider_time`={spider_time} where `address`={repr(id)};'
                self.rds.update(update_sql)
        if items:
            logger.info(f'rds刷新成功，{len(items)} 条')

    def schedule(self):
        """
        开始调度任务，数据落库
        """
        logger.info('爬虫定时调度任务开始')
        while True:
            self.data_to_rds()
            # 每半小时刷新一次
            time.sleep(30*60)