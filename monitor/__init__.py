from threading import Thread
from monitor.computer_resource.redis_m import RedisM
from monitor.computer_resource.mysql_m import MysqlM
from monitor.computer_resource.ecs import Ecs
from .twitterkol import Kol
from .insight_tgbot import run as insightbotrun
from .process_error import run as logerrorrun
from monitor.computer_resource.progresses_number import Processes
# from .telegram_message import client
from .server import PingDomain

def redis_():
    RedisM().run()

def mysql_():
    MysqlM().run()

def ecs_():
    Ecs().run()

def progresses_():
    Processes().run()

def run(name):
    if name == 'twitterkol':
        Kol().run()
    elif name == 'tginsightbot':
        insightbotrun()
    # 包括日志错误，进程死亡，进程夯住
    elif 'process_error' in name:
        logerrorrun(name)
    # elif name == 'tgmessage':
    #     client.run_until_disconnected()
    elif name == 'serverlive':
        PingDomain().monitor()
    else:
        # 硬件资源监控
        t_r = Thread(target=redis_)
        t_r.start()
        t_m  = Thread(target=mysql_)
        t_m.start()
        t_e  = Thread(target=ecs_)
        t_e.start()
        progresses_()