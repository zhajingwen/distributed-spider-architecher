from config import config
PROXY_URL = config.PROXY_URL

proxies = {
    'http': PROXY_URL,
    'https': PROXY_URL
}