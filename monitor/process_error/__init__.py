from .alllogs import Watch
from .process_dead import ProcessDead
from .process_stuck import ProcessStuck
from multiprocessing import Process

def dead():
    ProcessDead().run()
def stuck():
    ProcessStuck().run()

def run(name):
    if 'docker' not in name:
        print('进程死亡状态监控开始...')
        # 监控进程是否挂掉
        pdead = Process(target=dead)
        pdead.start()
    print('进程夯住状态监控开始...')
    # 监控进程是否夯住
    pstuck = Process(target=stuck)
    pstuck.start()
    print('进程异常错误监控开始...')
    # 监控日志异常
    Watch().run()
