content = """"""

for row in content.strip().split('\n'):
    if ' 历史vol24数据一共成功插入的天数' in row:
        if '(120)' not in row:
            alert_content = row.split('历史vol24数据')[-1]
            print(alert_content)




