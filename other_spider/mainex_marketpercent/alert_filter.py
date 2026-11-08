import os
import logging
import json
from utils.lark_bot import sender
from utils.redisdb import redis_cli
from .config import white_list

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Alert Filter')

class Alert:
    def __init__(self):
        # 所有的币都告警
        self.lark_api_aftergate = os.getenv('LARK_WEBHOOK_MAINEX_MARKETPERCENT', '')
        # 只有落后于Gate才告警
        self.lark_api_allcoins = os.getenv('LARK_WEBHOOK_MAINEX_MARKETPERCENT_2', '')

        self.fund_inner = os.getenv('LARK_WEBHOOK_MAINEX_MARKETPERCENT_3', '')

        self.redis_cli = redis_cli()
        self.base_key = 'mainexmarketpercent:filter:{}'


        # 排序告警+分类告警
        # 用于存放分类+排序规则的key
        # 公司资产部门做市（third party）
        thirdparty_key = 'mainexmarketpercent:marketing:thirdparty'
        # 项目方做市
        out_key = 'mainexmarketpercent:marketing:out'
        # BG内部做市
        inner_key = 'mainexmarketpercent:marketing:inner'
        #内部做市
        inner_marketing = self.redis_cli.get(inner_key)
        if inner_marketing:
            self.inner_marketing = json.loads(inner_marketing)
        else:
            self.inner_marketing = {}
        # 项目方做市
        out_marketing = self.redis_cli.get(out_key)
        if out_marketing:
            self.out_marketing = json.loads(out_marketing)
        else:
            self.out_marketing = {}
        # 三方做市
        thirdparty_marketing = self.redis_cli.get(thirdparty_key)
        if thirdparty_marketing:
            self.thirdparty_marketing = json.loads(thirdparty_marketing)
        else:
            self.thirdparty_marketing = {}

        # 用于存放分类后的待告警的数据的key
        self.inner_key_once = 'mainexmarketpercent:marketing:inner:once'
        self.out_key_once = 'mainexmarketpercent:marketing:out:once'
        self.thirdparty_key_once = 'mainexmarketpercent:marketing:thirdparty:once'
        self.white_list_key = 'mainexmarketpercent:whitelist'

    def alert_queue(self, webhook_type, url, symbol, content, key):
        """
        将需要排序告警的塞入redis队列，并返回True
        如果不需要返回False
        """
        if webhook_type == 'aftergate':
            # 内部做市
            if symbol in self.inner_marketing:
                url = self.fund_inner
                rank = self.inner_marketing[symbol]
                item = {
                    "content": content,
                    "url": url,
                    "symbol": symbol,
                    "rank": rank
                }
                self.redis_cli.sadd(self.inner_key_once, json.dumps(item))
                self.redis_cli.setex(key, 60*60, 1)
                logger.info(f'{symbol} 存入告警队列 Done')
                return True
            # 项目方做市
            elif symbol in self.out_marketing:
                rank = self.out_marketing[symbol]
                item = {
                    "content": content,
                    "url": url,
                    "symbol": symbol,
                    "rank": rank
                }
                self.redis_cli.sadd(self.out_key_once, json.dumps(item))
                self.redis_cli.setex(key, 60*60, 1)
                logger.info(f'{symbol} 存入告警队列 Done')
                return True
            # 三方做市
            elif symbol in self.thirdparty_marketing:
                url = self.fund_inner
                rank = self.thirdparty_marketing[symbol]
                item = {
                    "content": content,
                    "url": url,
                    "symbol": symbol,
                    "rank": rank
                }
                self.redis_cli.sadd(self.thirdparty_key_once, json.dumps(item))
                self.redis_cli.setex(key, 60*60, 1)
                logger.info(f'{symbol} 存入告警队列 Done')
                return True
            # 无法被分类的项目
            else:
                return
        return

    def alert(self, content, symbol, webhook_type):
        key = self.base_key.format(symbol)
        status = self.redis_cli.get(key)
        white_cache_list = self.redis_cli.smembers(self.white_list_key)
        if webhook_type == 'aftergate':
            url = self.lark_api_aftergate
        elif symbol in white_list:
            url = self.lark_api_aftergate
            webhook_type = 'aftergate'
        elif symbol in white_cache_list:
            url = self.lark_api_aftergate
            webhook_type = 'aftergate'
        else:
            url = self.lark_api_allcoins
        if not status:
            sorted_status = self.alert_queue(webhook_type, url, symbol, content, key)
            if not sorted_status:
                alert_status = sender(content, url, symbol)
                self.redis_cli.setex(key, 60*60, 1)
                logger.info(f'{symbol} 已告警 {alert_status}')
        else:
            logger.info(f'一小时内已告警过了：{symbol}')

