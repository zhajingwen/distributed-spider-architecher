import time
from datetime import datetime
import pymysql
from config import config


class MysqlTwistedPipepline(object):
    @classmethod
    def from_settings(cls, settings):
        dbparams = dict(
            host=config.MYSQL_HOST,
            db=config.MYSQL_DBNAME,
            user=config.MYSQL_USER,
            passwd=config.MYSQL_PASSWD,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            use_unicode=True
        )
        dbpool = pymysql.connect(**dbparams)
        return cls(dbpool)

    def __init__(self, dbpool):
        self.dbpool = dbpool
        self.cursor = self.dbpool.cursor()

    def process_item(self, item, spider):
        if item == None:
            return item
        # 使用twisted将mysql插入异步化
        # do = self.dbpool.runInteraction(self.do_insert, item)
        if "weibo" not in spider.name:
            return item
        # do.addErrback(self.handle_error, item)  # 处理异常
        pop_type = item.get("pop_type", None)
        if pop_type != "2":
            item['ext_fields'].pop("user_icon_b64")
            item['ext_fields'].pop("date")
            return item

        time_stamp = item["time"]
        self.dbpool.ping(reconnect=True)
        self.do_insert(self.cursor, item, spider)
        item["time"] = time_stamp
        item['ext_fields'].pop("user_icon_b64")
        item['ext_fields'].pop("date")
        item.pop("hot_index")
        return item

    def handle_error(self, failure, item):
        # 处理异步插入错误

        print("mysql do err -- ", failure, "---", item)

    def do_insert(self, cursor, item, spider):
        # item["user_icon_b64"] = ""
        now = datetime.now()
        item["content"] = item["content"].replace("'", "").replace('"', "")
        if type(item['time']) == int:
            timeArray = time.localtime(item['time'])
            otherStyleTime = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
            item["time"] = otherStyleTime
        item["hot_index"] = 0
        item = self.calculate_hot_blog(cursor, item,spider)
        if self.do_query(cursor, item, spider):
            # 执行update操作
            update_sql = """
                update {db_name} set up_count={up_count},comment_num={comment_num},reposts_num={reposts_num},user_icon_b64='{user_icon_b64}',update_at='{update_at}',hot_index={hot_index},time='{time}' where root_id='{root_id}' and date='{date}';
            """.format(db_name=spider.mysql_db_name,up_count=item['ext_fields']['up_count'],comment_num=item['ext_fields']['comment_num'],reposts_num=item['ext_fields']['reposts_num'],user_icon_b64=item['ext_fields']['user_icon_b64'],root_id=item['ext_fields']['root_id'], date=item['ext_fields']['date'], update_at=now, hot_index=item["hot_index"],time=item["time"])
            res = cursor.execute(update_sql)
            if not res:
                print("update popinion_nxx_weibo result ---", res)
                print("update sql == ", update_sql)
        else:
            # 执行insert操作

            insert_sql = """
                insert into {db_name}(blog_id,root_id,up_count,comment_num,reposts_num,parent_id,content,user_name,user_id,pop_type,time,url,date,pop_id,source_channel_id,user_icon_b64,update_at,hot_index)
                values ('{blog_id}','{root_id}',{up_count},{comment_num},{reposts_num},'{parent_id}','{content}','{user_name}','{user_id}','{pop_type}','{time}','{url}','{date}','{pop_id}','{source_channel_id}','{user_icon_b64}','{update_at}',{hot_index})
            """.format(
                db_name=spider.mysql_db_name,
                blog_id=item['ext_fields']["blog_id"],
                root_id=item['ext_fields']["root_id"],
                up_count=item['ext_fields']["up_count"],
                comment_num=item['ext_fields']["comment_num"],
                reposts_num=item['ext_fields']["reposts_num"],
                parent_id=item["parent_id"],
                content=item["content"],
                user_name=item["user_name"],
                user_id=item['ext_fields']["user_id"],
                pop_type=item["pop_type"],
                time=item["time"],
                url=item["url"],
                date=item['ext_fields']["date"],
                pop_id=item["pop_id"],
                source_channel_id=item["source_channel_id"],
                user_icon_b64=item['ext_fields']["user_icon_b64"],
                update_at=now,
                hot_index=item["hot_index"]
            )
            # print(insert_sql)
            res = cursor.execute(insert_sql)
            if not res:
                print("insert popinion_nxx_weibo result ---", res)
                print("insert sql == ", insert_sql)
        self.dbpool.commit()

    def do_query(self, cursor, item, spider):
        # today_date = get_today_date()
        query_sql = """select * from {db_name} where root_id='{root_id}' and date='{date}';
        """.format(db_name=spider.mysql_db_name,root_id=item['ext_fields']["root_id"], date=item['ext_fields']['date'])
        res = cursor.execute(query_sql)
        # print("do_query --", res)
        self.dbpool.commit()
        if res:
            return True
        else:
            return False

    def calculate_hot_blog(self, cursor, item, spider):
        today = item['ext_fields']['date']
        # yesterday = today.replace(today.year, today.month, today.day - 1, 0, 0, 0, 0)
        yesterday = datetime.fromtimestamp(today.timestamp() - 86400)
        query_sql = "select * from {db_name} where root_id='{root_id}' and date='{date}' order by update_at desc;".format(db_name=spider.mysql_db_name,root_id=item['ext_fields']["root_id"], date=yesterday)
        # print(query_sql)
        res = cursor.execute(query_sql)
        if res:
            result = cursor.fetchone()
            item["hot_index"] = item['ext_fields']["up_count"] + item['ext_fields']["comment_num"] + item['ext_fields']["reposts_num"] - result["up_count"] - result["comment_num"] - result["reposts_num"]
            if item["hot_index"] < 0:
                item["hot_index"] = 0
        else:
            item["hot_index"] = item['ext_fields']["up_count"] + item['ext_fields']["comment_num"] + item['ext_fields']["reposts_num"]
        self.dbpool.commit()
        return item
