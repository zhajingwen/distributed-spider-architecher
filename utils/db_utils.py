import logging
import pymysql
from pymysql.cursors import DictCursor
from traceback import format_exc
from config import config
from DBUtils.PooledDB import PooledDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MYSQL')

class DataUtils:
    def __init__(self, db=None):
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
            cursorclass=DictCursor
        )

    def insert(self, sql):
        ''' 插入数据库操作 '''
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            # 执行sql
            cursor.execute(sql)
            con.commit()
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            logger.error(f'插入失败：{sql}')
            con.rollback()
        finally:
            cursor.close()
            con.close()

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
        try:
            # 执行sql
            cursor.execute(sql)
            con.commit()
        except:
            # 发生错误时回滚
            logger.info(format_exc())
            con.rollback()
        finally:
            cursor.close()
            con.close()

    def update(self, sql):
        ''' 更新数据库操作 '''
        con = self.pool.connection()
        cursor = con.cursor()
        try:
            # 执行sql
            cursor.execute(sql)
            tt = cursor.execute(sql) # 返回 更新数据 条数 可以根据 返回值 判定处理结果
            logger.info(f'excute result {tt}')
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
            print('Error: unable to fecth data')
        finally:
            cursor.close()
            con.close()

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
        cursor.execute('''
        create table `gem_icon` (
            `address` varchar(100) not null,
            `icon` varchar(100),
            PRIMARY KEY (`address`)
        ) engine = InnoDB default charset = utf8mb4;
        ''')
        cursor.close()
        con.close()

