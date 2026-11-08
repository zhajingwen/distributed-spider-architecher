import logging
import json
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Sort')

class RouterAndExe:
    """
    路由指令
    执行指令
    """
    def __init__(self):
        self.redis_cli = redis_cli()

        # 用于存放分类+排序规则的key

        # 公司资产部门做市（third party）
        self.thirdparty_key = 'mainexmarketpercent:marketing:thirdparty'
        # 项目方做市
        self.out_key = 'mainexmarketpercent:marketing:out'
        # BG内部做市
        self.inner_key = 'mainexmarketpercent:marketing:inner'
        self.white_list_key = 'mainexmarketpercent:whitelist'

    def identy_cmd(self, cmd):
        """
        指令识别并分类
        """
        try:
            cmd = json.loads(cmd)
            category = cmd['category']
            if category == '资产部门做市':
                key = self.thirdparty_key
            elif category == '项目方做市':
                key = self.out_key
            else:
                # BG内部做市(ROBIN)
                key = self.inner_key
            rank_data = cmd['rank']
            # 将分类和排序数据放入redis
            self.redis_cli.set(key, json.dumps(rank_data))
            return '分类和排序规则已存储'
        except:
            return

    def insert_to_white_list(self, cmd):
        """
        将代币添加到redis内白名单
        """
        cmd = json.loads(cmd)
        rank_data = cmd['rank']
        with self.redis_cli.pipeline(transaction=False)as pipe:
            for symbol in rank_data:
                pipe.sadd(self.white_list_key, symbol)
            pipe.execute()

    def execute_cmd(self, cmd):
        """
        执行指令
        """
        status = self.identy_cmd(cmd)
        self.insert_to_white_list(cmd)
        if not status:
            exe_response = '执行失败，输入有误，请检查...'
        else:
            exe_response = '执行成功！'
        return exe_response
