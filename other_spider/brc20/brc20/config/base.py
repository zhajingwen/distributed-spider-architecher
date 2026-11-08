import os

class BaseConfig:
    REDIS_HOST = os.getenv('BRC20_DB_HOST', '')
    REDIS_PORT = 16379
    REDIS_PASSWORD = os.getenv('BRC20_REDIS_PASSWORD', '')
    REDIS_DB = 0
    REDIS_USERNAME = None

    # PROXY_URL = '<PROXY_URL>'
    # IP不限流量（每个IP100G）150个
    PROXY_URL = os.getenv('PROXY_URL', '')
    RDS_USER = 'root'
    RDS_PASSWORD = os.getenv('BRC20_RDS_PASSWORD', '')
    RDS_HOST = os.getenv('BRC20_DB_HOST', '')
    RDS_PORT = 13306
    RDS_DB = 'spider'

