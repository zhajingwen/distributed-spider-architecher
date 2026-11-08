import os
# IP不限流量（每个IP100G）150个
PROXY_URL = os.getenv('PROXY_URL', '')
# 格式化成 requests需要的格式类型
proxies = {
    'http': PROXY_URL,
    'https': PROXY_URL
}
