import json
import time
import logging
from playwright.sync_api import sync_playwright
from base64 import b64encode
from traceback import format_exc
from threading import Thread
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from other_spider.gem.free_mint.push_all_data import PushAllData

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GemList Spider')

class GemList:
    def __init__(self, duration):
        self.crypto_scan_job_key = 'crypto:scan:jobs_backup'
        self.num = 0
        self.rds = DataUtils('spider')
        self.table = 'gem'
        self.api_key = 'gem:api_key'
        self.redis_cli = redis_cli()
        self.job_key = 'gem:jobs_backup'
        self.url = f'https://www.gem.xyz/mints{duration}'
        self.push_all_data = PushAllData()
        self.freemint_jobs_key = 'gem:freemint:jobs_backup'
        self.icon_jobs = 'gem:icon:jobs_backup'

    def on_response(self,response):
        if response.url.split('gemlabs.xyz/')[-1] == 'analytics/minting':
            if response.request.method == 'POST':
                logger.info(f"mainlist {response.url}")
                payload = json.loads(response.request.post_data)
                # 时间区间
                duration = payload['filters']['duration']
                try:
                    # 可能存在body为None的情况，比如option请求
                    data = json.loads(response.body())
                except:
                    logger.info(f'option请求：{response.url}')
                    return
                all_update_sql_base = "replace into {}(collectionAddress,duration,firstMintAt," \
                                      "collectionName,top_wallets,mintCount,mintPrice," \
                                      "floorPrice,uniqueMintersPercentage,uniqueMinters,totalMintCount," \
                                      "mintTimeSeries,update_time) values{};"
                sql_values = []
                addresses = []
                # excute in assign time duration 24h
                # use redis to decoupling
                if duration == '24_hours':
                    pass
                    # self.redis_cli.sadd(self.freemint_jobs_key,json.dumps(data))
                # 图片下载并且存入sso
                if duration == '15_mins':
                    self.redis_cli.sadd(self.icon_jobs,json.dumps(data))
                for i in data['data']:
                    # try:
                    collectionAddress = i['collectionAddress']
                    # 将详情任务塞入redis
                    self.redis_cli.sadd(self.job_key,collectionAddress)
                    addresses.append(collectionAddress)
                    try:
                        mint_date = i['firstMintAt']
                    except:
                        # logger.error(i)
                        continue
                    # 可能存在没有collectionName的情况
                    name = i.get('collectionName','')
                    # if not name:
                    #     logger.error(f'have not collectionName: {i}')
                    #     continue
                    top_wallets = i['numPromininentMinters']
                    mintCount = i['mintCount']

                    # 可能存在空值的情况
                    if i.get('mintPrice'):
                        mintPrice = int(i['mintPrice'])/1000000000000000000
                        mintPrice = str(mintPrice)
                    else:
                        mintPrice = ''
                    if i.get('floorPrice'):
                        floorPrice = int(float(i['floorPrice']))/1000000000000000000
                        floorPrice = str(floorPrice)
                    else:
                        floorPrice = ''
                    uniqueMintersPercentage = i.get('uniqueMintersPercentage','NULL')
                    uniqueMinters = i.get('uniqueMinters','NULL')
                    totalMintCount = i.get('totalMintCount','NULL')
                    if totalMintCount != 'NULL':
                        totalMintCount = repr(str(totalMintCount))
                    # 默认得到的是一个列表的数据结构
                    mintTimeSeries = i['mintTimeSeries']
                    # 因为要存MySQL，所以要转成str类型
                    mintTimeSeries = json.dumps(mintTimeSeries)
                    mintTimeSeries = b64encode(mintTimeSeries.encode('utf-8')).decode('utf-8')
                    update_sql = f"('{collectionAddress}','{duration}',{mint_date},{repr(name)}," \
                                 f"{top_wallets},{mintCount},'{mintPrice}','{floorPrice}',{uniqueMintersPercentage}," \
                                 f"{uniqueMinters},{totalMintCount},'{mintTimeSeries}',{int(time.time())})"
                    sql_values.append(update_sql)
                # 可能一条记录也没有，则就为空了，会导致SQL报错
                if sql_values:
                    # 多条记录一次性插入
                    all_update_sql = all_update_sql_base.format(self.table, ','.join(sql_values))
                    self.rds.insert(all_update_sql)
                # 将apikey写入redis提供给详情页使用
                api_key = response.request.headers['x-api-key']
                self.redis_cli.set(self.api_key,api_key)
        if 'analytics/minting/pending' in response.url:
            if response.request.method == 'POST':
                logger.info(f"update numPendingTxs {response.url}")
                try:
                    # 可能存在body为None的情况，比如option请求
                    data = json.loads(response.body())
                except:
                    logger.info(f'option请求：{response.url}')
                    return
                data = data['data']
                for d in data:
                    address = d['address']
                    # pending transactons 就是前面黄色的转圈圈的东西
                    numPendingTxs = d['numPendingTxs']
                    update_sql = f"update {self.table} set numPendingTxs={numPendingTxs},update_time={int(time.time())} where collectionAddress={repr(address)};"
                    self.rds.insert(update_sql)

    def browser(self, restart_duration):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # 抓包程序，类似于挂载脚本抓包，解析包内容
            page.on('response', self.on_response)
            # 永久等待 但是ERR_CONNECTION_REFUSED这种类型的错误会导致浏览器立马出现异常
            page.goto(self.url, timeout=0)
            # timeout=0表示永远不超时，以此来确保标签页和浏览器都不会关闭
            # 根据实际情况一段时间要重启一次，否则占用内存过大
            page.wait_for_function("() => window.x > 0", timeout=1000*restart_duration)

    def run(self):
        start = int(time.time())
        # 每小时重启一次  实际测试发现可能55分钟就会存在卡死的情况
        # 改成50分钟
        restart_duration = 50*60
        while True:
            try:
                self.browser(restart_duration)
                # 实际上上面会阻塞，永远都不会执行到break这里
                break
            except:
                logger.info(f'浏览器运行时间：{int(time.time())-start}')
                start = int(time.time())
                # 并非主动想抛出的异常
                if 'TimeoutError' not in format_exc():
                    logger.error(format_exc())
                    logger.error('浏览器加载失败，重试...')
                else:
                    logger.info('清空缓存，重启浏览器...')
                time.sleep(10)

    def creat(self):
        self.rds.create_table()