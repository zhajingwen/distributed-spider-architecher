import os
from .local import *
from .prod import *
from.test import *
from .pre import *
env = os.environ.get('env')

# 如果没有环境，默认是线上
if not env:
    env = 'prod'

config = {
    'local':LocalConfig,
    'dev': LocalConfig,
    'daren_connect': TestConfig,
    'prod':ProdConfig,
    'test':TestConfig,
    'pre':PreConfig
}

config = config[env]()
