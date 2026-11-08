from hashlib import md5

def insert_data_worldwide(data, spider_date, rds, spider_time):
    table = 'google_trends_worldwide'
    all_update_sql_base = "replace into {} values{};"
    sql_values = []
    for d in data:
        related_words = d['query']
        value = d['value']
        value = round(value/100,2)
        # 存在一大段句子的情况
        if len(related_words) > 100:
            continue
        if len(related_words.split(' ')) > 5:
            continue
        id = md5(f'{spider_date}{related_words}'.encode('utf-8')).hexdigest()
        update_sql = f"({repr(id)},{repr(related_words)},{value},{spider_time},{repr(spider_date)})"
        sql_values.append(update_sql)
    if not data:
        return
    if sql_values:
        # 多条记录一次性插入
        all_update_sql = all_update_sql_base.format(table, ','.join(sql_values))
        rds.insert(all_update_sql)
        return True

