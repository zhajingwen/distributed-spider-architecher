import logging
import pymysql
from pymysql.cursors import DictCursor
from traceback import format_exc
from config import config
from DBUtils.PooledDB import PooledDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MYSQL')

class DataUtils:
    def __init__(self, db='spider'):
        '''初始化数据库信息并创建数据库连接'''
        self.host = config.RDS_HOST
        self.username = config.RDS_USER
        self.password = config.RDS_PASSWORD
        self.database = db
        self.port = config.RDS_PORT
        limit_count = 3  # 最低预启动数据库连接数量
        self.pool = PooledDB(
            pymysql,
            limit_count,
            host = self.host,
            user = self.username,
            passwd = self.password,
            db = db,
            port = self.port,
            # charset = self.charset,
            charset='utf8mb4',
            use_unicode = True,
            cursorclass=DictCursor,
            # maxconnections=100,
            connect_timeout=300
        )

    def insert(self, sql):
        ''' 插入数据库操作 '''
        con = self.pool.connection()
        cursor = con.cursor()
        status = False
        try:
            # 执行sql
            cursor.execute(sql)
            con.commit()
            status = True
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            logger.error(f'插入失败：{sql}')
            con.rollback()
        finally:
            cursor.close()
            con.close()
            return status

    def execute_many(self, sql, args):
        ''' 插入数据库操作 '''
        # 检查连接是否断开，如果断开就进行重连
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            # 执行sql
            cursor.executemany(sql, args)
            con.commit()
        except:
            # 发生错误时回滚
            # traceback.print_exc()
            con.rollback()
        finally:
            cursor.close()
            con.close()

    def delete(self, sql):
        ''' 操作数据库数据删除 '''
        con = self.pool.connection()
        cursor = con.cursor()
        status = False
        try:
            # 执行sql
            cursor.execute(sql)
            con.commit()
            status = True
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            logger.info(sql)
            con.rollback()
        finally:
            cursor.close()
            con.close()
            return status

    def update(self, sql):
        ''' 更新数据库操作 '''
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            # 执行sql
            cursor.execute(sql)
            # cursor.execute(sql)
            # tt = cursor.execute(sql) # 返回 更新数据 条数 可以根据 返回值 判定处理结果
            # logger.info(f'excute result {tt}')
            con.commit()
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            con.rollback()
        finally:
            cursor.close()
            con.close()

    def select(self, sql):
        ''' 数据库查询 '''
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()  # 返回所有记录列表
        except:
            logger.info(format_exc())
            logger.error(sql)
        finally:
            cursor.close()
            con.close()

    def update_many(self, query, data):
        ''' 更新数据库操作 '''
        con = self.pool.connection()
        cursor = con.cursor()
        status = False
        try:
            # 执行批量更新操作
            tt = cursor.executemany(query, data)
            logger.info(f'excute result {tt}')
            con.commit()
            status = True
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            con.rollback()
        finally:
            cursor.close()
            con.close()
            return status

    def select_dictcursor(self, sql):
        ''' 数据库查询 '''
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()  # 返回所有记录列表
        except:
            logger.info(format_exc())
        finally:
            cursor.close()
            con.close()

    def closeDb(self):
        ''' 数据库连接关闭 '''
        self.pool.close()

    def connection(self):
        """返回数据库连接"""
        con = self.pool.connection()
        return con

    def create_db(self,dbname):
        # 创建游标
        con = self.pool.connection()
        cursor = con.cursor()
        cursor.execute('show databases')
        print('当前数据库列表')
        for item in cursor.fetchall():
            print(item)
        try:
            # 执行sql查询语句
            cursor.execute(f"create database {dbname}")
            print('数据库创建成功')
            # 关闭游标
            cursor.close()
            # 关闭数据库连接
            con.close()
        except pymysql.err.MySQLError as _error:
            print('数据库创建失败')
            raise _error

    def create_table(self, dbname='spider'):
        con = self.pool.connection()
        cursor = con.cursor()
        # 使用库
        cursor.execute(f"use {dbname};")
        # 建表
        # cur.execute('''
        # create table `cmc_price_alert11` (
        #     `token_id` varchar(45) not null default '',
        #     `price` varchar(45) not null default '',
        #     `spider_time` int,
        #     PRIMARY KEY (`token_id`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # cur.execute('''
        # create table `crypto_scan` (
        #     `id` varchar(45) not null default '',
        #     `blockchain` varchar(45) not null default '',
        #     `address` varchar(50) not null default '',
        #     `names` text not null,
        #     `tags` text not null,
        #     PRIMARY KEY (`id`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # cur.execute('''
        # create table `gem` (
        #     `collectionAddress` varchar(50),
        #     `duration` varchar(45),
        #     `firstMintAt` int,
        #     `numPendingTxs` int,
        #     `collectionName` varchar(500),
        #     `top_wallets` int,
        #     `mintCount` int,
        #     `mintPrice` varchar(45),
        #     `floorPrice` varchar(45),
        #     `uniqueMintersPercentage` float,
        #     `uniqueMinters` int,
        #     `totalMintCount` int,
        #     `mintTimeSeries`  text,
        #     `externalUrl` varchar(100),
        #     `discordUrl` varchar(100),
        #     `twitterUsername` varchar(45),
        #     `list_origin` TEXT,
        #     `detail_origin` TEXT,
        #     `update_time` int,
        #     PRIMARY KEY (`collectionAddress`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # cur.execute('''
        #  create table `twitterscan_kol` (
        #      `id` varchar(50),
        #      `username` varchar(100),
        #      `coin_name` varchar(100),
        #      `token_count` int,
        #      `tag` varchar(45),
        #      `spider_time` int,
        #      `spider_date` varchar(45),
        #      PRIMARY KEY (`id`)
        #  ) engine = InnoDB default charset = utf8mb4;
        #  ''')
        # cursor.execute('''
        # create table `cmc_history` (
        #     `id` varchar(100) not null,
        #     `slug` varchar(100) not null,
        #     `name` varchar(100),
        #     `symbol` varchar(100),
        #     `Date` varchar(100),
        #     `Open` varchar(100),
        #     `High` varchar(100),
        #     `Low` varchar(100),
        #     `Close` varchar(100),
        #     `Volume` varchar(100),
        #     `MarketCap` varchar(100),
        #     PRIMARY KEY (`id`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # cursor.execute('''
        # create table `nswap` (
        #     `id` int not null,
        #     `collection` varchar(100),
        #     `twitter` int,
        #     `discord` int,
        #     `pre_sale_date` varchar(100),
        #     `public_mint_date` varchar(100),
        #     `max_supply` int,
        #     `website` varchar(100),
        #     `description` text,
        #     `pre_sale_Mint_price` float,
        #     `public_mint_price` float,
        #     PRIMARY KEY (`id`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # cursor.execute('''
        # create table `nswap_raffles` (
        #     `id` int not null,
        #     `collection` varchar(100),
        #     `twitter` int,
        #     `winner` int,
        #     `countdown` varchar(100),
        #     `chain` varchar(100),
        #     `website` varchar(100),
        #     `description` text,
        #     `mint_date` varchar(50),
        #     `update_time` int,
        #     PRIMARY KEY (`id`)
        # ) engine = InnoDB default charset = utf8mb4;
        # ''')
        # sql = '''
        # create table `dexfilter_user_a_a` (
        #     `address` varchar(100),
        #     `dexfilter_id` varchar(500),
        #     `chain` varchar(100),
        #     `total_name` varchar(100),
        #     `symbol` varchar(100),
        #     `price` float,
        #     `flow_pool` float,
        #     `candle_url` varchar(500),
        #     `analysis_url` varchar(500),
        #     `scan_url` varchar(100),
        #     `tg_url` varchar(100),
        #     `twitter_url` varchar(100),
        #     `pool_url` varchar(100),
        #     `discord_url` varchar(100),
        #     `web_url` varchar(100),
        #     `wb` float,
        #     `ub` float,
        #     `total_value` float,
        #     `supply` float,
        #     `high_price` float,
        #     `low_price` float,
        #     `holders` int,
        #     `is_honeypot` varchar(100),
        #     `BuyGas` float,
        #     `SellGas` float,
        #     `BuyTax` float,
        #     `SellTax` float,
        #     `is_mintable` varchar(100),
        #     `lp_holder_count` int,
        #     `is_anti_whale` varchar(100),
        #     `sell_tax` float,
        #     `buy_tax` float,
        #     `slippage_modifiable` varchar(100),
        #     `is_open_source` varchar(100),
        #     `can_take_back_ownership` varchar(100),
        #     `cannot_sell_all` varchar(100),
        #     `trading_cooldown` varchar(100),
        #     `transfer_pausable` varchar(100),
        #     `is_blacklisted` varchar(100),
        #     `is_proxy` varchar(100),
        #     `is_whitelisted` varchar(100),
        #     `r5m` float,
        #     `r1h` float,
        #     `r4h` float,
        #     `r24h` float,
        #     `spider_date_h` varchar(100),
        #      PRIMARY KEY (`address`)
        # ) engine = InnoDB default charset = utf8mb4;
        # '''
        # sql = '''
        #                 create table `dexfilter_user_a_b` (
        #                     `address` varchar(100),
        # 		            `newholders_5m` int,
        # 					`txns_5m` int,
        # 					`buys_5m` int,
        # 					`sells_5m` int,
        # 					`vns_5m` float,
        # 					`newholders_1m` int,
        # 					`txns_1h` int,
        # 					`buys_1h` int,
        # 					`sells_1h` int,
        # 					`vns_1h` float,
        # 					`newholders_4h` int,
        # 					`txns_4h` int,
        # 					`buys_4h` int,
        # 					`sells_4h` int,
        # 					`vns_4h` float,
        # 					`newholders_24h` int,
        # 					`txns_24h` int,
        # 					`buys_24h` int,
        # 					`sells_24h` int,
        # 					`vns_24h` float,
        #         			`spider_date_h` varchar(100),
        #         			`dexfilter_id` varchar(500),
        #                      PRIMARY KEY (`address`)
        #                 ) engine = InnoDB default charset = utf8mb4;
        #                 '''
        # sql = '''
        #                 create table `dexfilter_user_a_c` (
        #                     `address` varchar(100),
        # 		            `totalname` varchar(100),
        # 		            `symbol` varchar(100),
        # 		            `pair` varchar(100),
        # 		            `swap` varchar(100),
        # 					`ub` float,
        # 					`vn` float,
        #         			`spider_date_h` varchar(100),
        #         			`dexfilter_id` varchar(500),
        #         			`address_addresss` varchar(500),
        #                      PRIMARY KEY (`address`)
        #                 ) engine = InnoDB default charset = utf8mb4;
        #                 '''
        # sql = '''
        #                 create table `cmc_backtest_btc` (
        #                     `timestamp` int,
        # 		            `value` varchar(300),
        #                      PRIMARY KEY (`timestamp`)
        #                 ) engine = InnoDB default charset = utf8mb4;
        #                 '''
        sql = '''
                        create table `coingecko2` (
                            `uuid` varchar(100),                                                
                            `id` varchar(300),                        
                            `name` varchar(300),
                            `symbol` varchar(300),
                            `marketpair` varchar(300),
                            `volume` double,
                            `datadate` varchar(50),
                            `datatimestamp` int,
                            `spider_time` int,
                             PRIMARY KEY (`uuid`)
                        ) engine = InnoDB default charset = utf8mb4;
                        '''
        cursor.execute(sql)
        cursor.close()
        con.close()

