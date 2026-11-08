import sqlite3

conn = sqlite3.connect("logv2_202007.db")
cursor = conn.cursor()
sql = """select name from sqlite_master where type='table' order by name"""
cursor.execute(sql)
result = cursor.fetchall()
print(result)
print(type(result))
conn.close()




import sqlite3
conn = sqlite3.connect("logv2_202007.db")
cursor = conn.cursor()
sql = """pragma table_info(log)"""
cursor.execute(sql)
result = cursor.fetchall()
print(result)
print(type(result))
# (4256, 1595904768, 12, '酷Q', '√ 0.01s', '[↓]群组消息', '群: 710894006 帐号: 3385018433 \r\n感觉我官服预约的太晚了')
# sql = "select * from log"
# cursor.execute(sql)
# all = cursor.fetchall()
# for i in all:
#     print(i)

conn.close()
