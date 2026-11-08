import logging
from .coinsadjust import Adjust
from .sort import Sort

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MarkertShare Router')

def function_router(cmd):
    if 'marketshare-coinsadjust-' in cmd:
        cmd = cmd.replace('marketshare-coinsadjust-', '')
        # 执行新增或删除代币的任务
        exe_response = Adjust().execute_cmd(cmd)
    elif 'marketshare-sort/' in cmd:
        cmd = cmd.replace('marketshare-sort/', '')
        exe_response = Sort().execute_cmd(cmd)
    else:
        logger.warning(f'指令有误: {cmd}')
        exe_response = '指令错误！'
    return exe_response