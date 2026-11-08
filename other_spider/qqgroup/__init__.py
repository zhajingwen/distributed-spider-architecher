from other_spider.qqgroup.webhook.group import app
from other_spider.qqgroup.mirai_kotlin.run import init_setting
from config import config
import os
def run(spider_name):
    if (spider_name == "mirai") or ("mirai" in spider_name):
        if "backup" in spider_name:
            account = config.QQ_ACCOUNT_BACKUP
        else:
            account = config.QQ_ACCOUNT
        init_setting()
        os.system("mv other_spider/qqgroup/mirai_kotlin/* ./")
        account = account.split(' ')
        user = account[0]
        password = account[1]
        os.system(f"java -jar onebot-kotlin-0.3.4-all.jar --account {user} --password {password}")
    else:
        # 事件上报接口
        app.run(host='0.0.0.0',port=5003)