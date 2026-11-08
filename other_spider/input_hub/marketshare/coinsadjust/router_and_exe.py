import logging
import json
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Route')

class RouterAndExe:
    """
    路由指令
    执行指令
    """
    def __init__(self):
        self.redis_cli = redis_cli()
        self.jobs_key = 'mainexmarketpercent:jobs'

    # def get_name(self, symbol):
    #     """
    #     匹配代币的名称
    #     """
    #     # 根据Symbol匹配ID
    #     symbol_ids = 'mainex:symbolids'
    #     symbol_id_map_data = self.redis_cli.hgetall(symbol_ids)
    #     id = symbol_id_map_data.get(symbol)
    #     if not id:
    #         id = symbol_id_map_data.get(symbol.upper())
    #     if id:
    #         # 根据ID匹配name
    #         id_names_key = 'mainex:idsnames'
    #         id_name_map_data = self.redis_cli.hgetall(id_names_key)
    #         name = id_name_map_data.get(id)
    #         logger.info(f'基于mainex交易所从symbol: {symbol}成功匹配到name：{name}')
    #         return name
    #     else:
    #         logger.warning(f'symbol异常,无法匹配name：{symbol}')
    #         return

    def delete_job(self, cmd_target):
        """
        从 redis 删除某个代币
        """
        symbol = cmd_target['symbol']
        logger.info(f'添加代币程序检测到代币简称：{symbol}')
        # name = self.get_name(symbol)
        name = cmd_target['name']
        if name:
            cmd_target["name"] = name
            self.redis_cli.hdel(self.jobs_key, name)
            return cmd_target
        else:
            return

    def add_job(self, cmd_target):
        symbol = cmd_target['symbol']
        logger.info(f'添加代币程序检测到代币简称：{symbol}')
        # name = self.get_name(symbol)
        name = cmd_target['name']
        if name:
            cmd_target["name"] = name
            self.redis_cli.hset(self.jobs_key, name, json.dumps(cmd_target))
            return cmd_target
        else:
            return

    def identy_cmd(self, cmd):
        """
        指令识别并分类
        """
        cmd = cmd.strip()
        if '/' in cmd:
            cmd_ = cmd.split('/')
            cmd_type = cmd_[0]
            cmd_target = cmd_[1]
            try:
                cmd_target = json.loads(cmd_target)
            except:
                logger.error(f'指令错误：{cmd}')
                return
            if cmd_type == 'add':
                status = self.add_job(cmd_target)
                return status
            elif cmd_type == 'del':
                status = self.delete_job(cmd_target)
                return status
            else:
                logger.error(f'指令错误：{cmd}')
                return

    def execute_cmd(self, cmd):
        """
        执行指令
        """
        try:
            status = self.identy_cmd(cmd)
            if not status:
                exe_response = '执行失败，输入有误，请检查...'
            else:
                exe_response = '执行成功！'
        except:
            exe_response = '执行失败，输入有误，请检查...'
        return exe_response
