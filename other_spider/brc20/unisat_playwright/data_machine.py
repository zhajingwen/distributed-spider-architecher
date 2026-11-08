import datetime
import logging
import os
from traceback import format_exc
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Data machine')
env = os.environ.get('env')


class Unisat:
    def __init__(self):
        # self.base_url = 'https://unisat.io/brc20-api-v2/brc20/status?ticker=&start={}&limit=500&complete=&sort=minted'
        self.base_url = 'https://api.unisat.io/query-v4/brc20/status?ticker_hex=&start={}&limit=20&complete=&sort=minted'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
        self.rds = DataUtils()
        self.redis_cli = redis_cli()
        self.unisat_done = 'crawl-brc20:unisat_playwright:done'
        self.cookies_store = 'crawl-brc20:unisat_playwright:cookies'
        self.lark_url = os.getenv('LARK_WEBHOOK_BRC20', '')
        self.black_list = 'crawl-brc20:unisat_playwright:alert:blacklist'
        self.stop_turn_page = 'crawl-brc20:unisat_playwright:stopturnpage'
        # 测试用
        self.processing_holders_trx = 300

    def parse(self, data):
        data = data['data']
        # start_time = int(time.time())
        update_query = 'UPDATE brc20_unisat SET holders_amount=%s,online_time=%s,' \
                       'update_time=now(),transactions=%s,transaction_24h=%s,' \
                       'progress_24h=%s,mint_progress=%s WHERE name=%s'
        update_data = []

        repalce_into_sqls = 'replace into brc20_unisat values {};'
        insert_data = []
        names = []
        detail = data['detail']
        for item in detail:
            name = item['ticker']
            name = name.lower()
            holdersCount = item['holdersCount']
            deployBlocktime = item['deployBlocktime']

            # 进入首页的数据可能会导致合理误判
            # 当检测当前页transactions数量小于300时就没有必要翻页了，列表页是根据 transactions 降序排列的
            # transactions = item['historyCount']
            # if transactions < self.processing_holders_trx:
            #     self.redis_cli.set(self.stop_turn_page, 1)
            #     logger.info(f'最后一页 transactions 数量： {transactions}')
            #     return

            progress = (item['completeHeight'] / item['deployHeight']) * 100
            if progress > 100:
                progress = 100
            if progress < 1:
                progress = 0
            transactions = item['historyCount']
            dt_object = datetime.datetime.fromtimestamp(deployBlocktime)
            deploy_date = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            # 是否插入过
            have_insert_status = self.redis_cli.sismember(self.unisat_done,name)
            # 插入过，用update语法
            if have_insert_status:
                # 由于不统计transactions_24h ，progress_24h 故这里都设置为0
                update_one_data = (holdersCount, deploy_date, transactions, 0, 0, progress, name)
                update_data.append(update_one_data)
                names.append(name)
            # 没插入过，用insert语法
            else:
                insert_sql = f'({repr(name)},{progress},{holdersCount},{repr(deploy_date)},{transactions},null,null,now(),now())'
                insert_data.append(insert_sql)
                names.append(name)
                # 跳过update处理
                # continue
            # # 查询历史数据计算24小时新增量
            # res_24h = self.gen_24h_data(name, progress, transactions)
            # if res_24h:
            #     # 24小时数据（数据库查询到的）
            #     progress_24h, transactions_24h = res_24h
                # 组合数据批量更新

            # 规则过滤 + 推送到lark
            self.alert(item)
        # 执行update操作
        if update_data:
            # 测试任务不设定早上刷新
            if env == 'test':
                self.update_mysql_test(update_query, update_data, names)
            # 线上生产
            else:
                # 每日7点-7点59分分才更新一次
                self.update_mysql(update_query, update_data, names)

        # 插入随时进行不需要在早上固定时间段
        if insert_data:
            sqls = ','.join(insert_data)
            new_insert_sqls = repalce_into_sqls.format(sqls)
            status = self.rds.insert(new_insert_sqls)
            if status:
                # 首次插入后记录到redis
                with self.redis_cli.pipeline(transaction=False)as pipe:
                    for name in names:
                        pipe.sadd(self.unisat_done,name)
                    pipe.execute()
        # logger.info(f'page: {num} 耗时：{int(time.time()) - start_time} s')

    def update_mysql(self, update_query, update_data, names):
        """
        由于要算24H mint进度数据，故数据库24小时刷新一次
        """
        today_now = datetime.datetime.now()
        today_at_07 = today_now.replace(hour=7, minute=0, second=0)
        today_at_07_59 = today_now.replace(hour=7, minute=59, second=0)
        # 每日07点刷新一次unisat数据
        if today_at_07 < today_now < today_at_07_59:
            status = self.rds.update_many(update_query, update_data)
            # 插入成功
            if status:
                logger.info(f'update successfully {names}')
            else:
                logger.error(f'update failed {names}')

    def update_mysql_test(self, update_query, update_data, names):
        """
        由于要算24H mint进度数据，故数据库24小时刷新一次
        """
        # 入库返回值
        status = self.rds.update_many(update_query, update_data)
        # 插入成功
        if status:
            logger.info(f'update successfully {names}')
        else:
            logger.error(f'update failed {names}')

    # def gen_24h_data(self, name, progress, transactions):
    #     """
    #     生成24小时转账次数
    #     24小时mint进度
    #     """
    #     # if '"' in name:
    #     #     name = name.replace()
    #     sql = f'select mint_progress,transactions from brc20_unisat where name={repr(name)};'
    #     result = self.rds.select(sql)
    #     if result:
    #         result = result[0]
    #         old_mint_progress = result['mint_progress']
    #         if old_mint_progress:
    #             # TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'
    #             # progress_24h = progress - old_mint_progress
    #             progress_24h = progress - float(old_mint_progress)
    #         else:
    #             progress_24h = progress
    #         old_transactions = result['transactions']
    #         if old_transactions:
    #             transactions_24h = transactions - float(old_transactions)
    #         else:
    #             transactions_24h = transactions
    #         return progress_24h, transactions_24h
    #     else:
    #         return None


    def rule_judge1(self, data):
        """
        条件1
        通过 返回True
        """
        status = False
        deploy_blocktime = data['deployBlocktime']
        #  部署时间 在23年3月1日以后 1677600000
        # if int(time.time()) - deploy_blocktime < 7 * 24 * 60 * 60:
        if deploy_blocktime > 1677600000:
            # mint进度约束
            progress = (float(data['minted']) / float(data['max'])) * 100
            if progress >= 20 and progress < 100:
                if progress > 100:
                    progress = 100
                holders = data['holdersCount']
                # holders约束
                if holders >= self.processing_holders_trx:
                    transactions = data['historyCount']
                    # transactioins约束
                    if transactions >= self.processing_holders_trx:
                        status = True
        # if not status:
        #     logger.error(f'条件不符合 {data}')
        return status

    def rule_judge2(self, data):
        """
        条件2
        通过 返回True
        """
        status = False
        deploy_blocktime = data['deployBlocktime']
        #  部署时间 在23年3月1日以后 1677600000
        # if int(time.time()) - deploy_blocktime < 7 * 24 * 60 * 60:
        if deploy_blocktime > 1677600000:
            # mint进度约束
            progress = (float(data['minted']) / float(data['max'])) * 100
            if progress > 100:
                progress = 100
            if progress == 100:
                holders = data['holdersCount']
                # holders约束
                if holders >= 500:
                    transactions = data['historyCount']
                    # transactioins约束
                    if transactions >= 1000:
                        status = True
        return status

    def alert(self, data):
        """
        调用规则判断且发送告警
        lark 推送
        """
        deploy_blocktime = data['deployBlocktime']
        # progress = (data['completeHeight'] / data['deployHeight']) * 100
        progress = (float(data['minted']) / float(data['max'])) * 100
        if progress > 100:
            progress = 100
        progress = int(progress)
        holders = data['holdersCount']
        transactions = data['historyCount']
        ticker = data['ticker']
        ticker = ticker.lower()
        dt_object = datetime.datetime.fromtimestamp(deploy_blocktime)
        # 将datetime对象转换成字符串
        date_string = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        # 只要有一个条件满足就报警
        if self.rule_judge1(data) or self.rule_judge2(data):
            if self.redis_cli.sismember(self.black_list,ticker):
                logger.info(f'告警过了：{ticker}')
                return
            content = f"""
            币名：{ticker}
            部署具体时间：{date_string}
            mint总进度：{progress}%
            Holder：{holders}
            Transation：{transactions}
            """
            if progress < 100:
                # 有可能KEY不存在
                try:
                    totalMinted = data['totalMinted']
                    minting_in_memory = float(totalMinted) - float(data['confirmedMinted'])
                    limit_per_mint = float(data['limit'])
                    minting = int(minting_in_memory/limit_per_mint)
                    progress_new = f"{totalMinted} / {data['max']}"
                    confirmedMintedbefore24h = int(float(data['confirmedMinted24h']))
                    confirmedbetween1hand24h = int(float(data['confirmedMinted1h'])) - confirmedMintedbefore24h
                    confirmedin1hour = int(float(data['confirmedMinted'])) - int(float(data['confirmedMinted1h']))
                    content = f"""
                     币名：{ticker}
                     部署具体时间：{date_string}
                     mint总进度：{progress}%
                     Holder：{holders}
                     Transation：{transactions}
                     Minting: {minting}
                     Progress: {progress_new}
                     Confirmed before 24h: {confirmedMintedbefore24h}
                     Confirmed in 1-24h: {confirmedbetween1hand24h}
                     Confirmed in 1h: {confirmedin1hour}
                     In memory pool: {minting_in_memory}
                     """
                except:
                    logger.error(format_exc())

            sender(content, self.lark_url, 'brc20')
            # 报警后加入去重队列
            self.redis_cli.sadd(self.black_list,ticker)

                        # res_24h = self.gen_24h_data(ticker, progress, transactions)
                        # if res_24h:
                        #     progress_24h, transactions_24h = res_24h
                        #     if progress_24h >= 10:
                        #         content = f"""
                        #         币名：{ticker}
                        #         部署具体时间：{date_string}
                        #         mint总进度：{progress}%
                        #         24H增加进度值：{progress_24h}%
                        #         当日转账次数：{transactions_24h}
                        #         Holder：{holders}
                        #         Transation：{transactions}
                        #         """
                        #         sender(content, self.lark_url, 'brc20')
                        # if res_24h:
                        #     progress_24h, transactions_24h = res_24h
                        #     if progress_24h >= 10:
