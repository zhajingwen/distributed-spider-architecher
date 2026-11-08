import os


def _int(name, default):
    value = os.getenv(name)
    return int(value) if value else default


# 默认公共配置：所有敏感信息均从环境变量读取，参见项目根目录 .env.example
class BaseConfig:
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
    REDIS_PORT = _int('REDIS_PORT', 6379)
    REDIS_USERNAME = os.getenv('REDIS_USERNAME') or None
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD') or None
    REDIS_DB = _int('REDIS_DB', 0)

    # MySQL / RDS
    RDS_HOST = os.getenv('RDS_HOST', '127.0.0.1')
    RDS_PORT = _int('RDS_PORT', 3306)
    RDS_USER = os.getenv('RDS_USER', 'root')
    RDS_PASSWORD = os.getenv('RDS_PASSWORD', '')

    # HTTP 代理，格式：http://username:password@proxyhost:port
    PROXY_URL = os.getenv('PROXY_URL', '')

    # cf_clearance 远程调用服务地址
    CF_RPC = os.getenv('CF_RPC', 'localhost')

    # 阿里云 SLS 日志服务
    ENDPOINT = os.getenv('ALIYUN_SLS_ENDPOINT', '')
    ACCESSKEYID = os.getenv('ALIYUN_ACCESS_KEY_ID', '')
    ACCESSKEY = os.getenv('ALIYUN_ACCESS_KEY_SECRET', '')
    PROJECT = os.getenv('ALIYUN_SLS_PROJECT', '')
    LOGSTORE = os.getenv('ALIYUN_SLS_LOGSTORE', '')
