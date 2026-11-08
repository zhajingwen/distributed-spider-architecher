import os
import time
import requests
import re
import json
from utils.redisdb import redis_cli


def parse_proxy(proxy):
    """
    格式化
    """
    if "@" in proxy:
        proxy_regex = re.match("(.+)://(.+):(.+)@(.+)", proxy)
        server = f"{proxy_regex.group(1)}://{proxy_regex.group(4)}"

        proxy_params = {
            "server": server,
            "username": proxy_regex.group(2),
            "password": proxy_regex.group(3),
        }
    else:
        proxy_params = {"server": proxy}

    return proxy_params



def check_ips():
    ip_store_key = 'dexfilter:ips:store'
    cookies_store = 'dexfilter:cookies'
    redis_c = redis_cli()
    ips = redis_c.hgetall(ip_store_key)
    for id in ips:
        ip = ips[id]
        proxy_url = ip
        browser_proxy = parse_proxy(proxy_url)
        start = int(time.time())
        resp = requests.post("http://" + os.getenv('CF_RPC_HOST', '') + ":80/challenge",
                             json={"proxy": browser_proxy, "timeout": 15,
                                   "url": "https://dexfilter.com/"})
        res = resp.json()
        if not res.get("success"):
            redis_c.hdel(ip_store_key,id)
            print(f'代理失败，删除{id}：{ip}')
        else:
            cookie_seed = {
                "id":id,
                "proxy": ip,
                "ua": res['user_agent'],
                "cf": res['cookies']['cf_clearance'],
                "timestamp": int(time.time())
            }
            redis_c.sadd(cookies_store,json.dumps(cookie_seed))




