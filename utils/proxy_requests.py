from config import config
# 格式化成 requests需要的格式类型
proxies = {
    'http': config.PROXY_URL,
    'https': config.PROXY_URL
}
