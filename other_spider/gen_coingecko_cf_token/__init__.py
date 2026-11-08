import logging
from .ips.to_redis import IpStore
from .cookies.gen_cookies import Gen

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Fuck Coingecko CF')

def run(spider_name):
    project_name = 'coingecko'
    if spider_name == 'ipmonitor':
        IpStore(project_name).ipstore_monitor()
    else:
        # gencookies
        # url = 'https://www.coingecko.com/en/coins/marblex'
        # url = 'https://www.coingecko.com/en/search_v2?query=marblex'
        # 这是一个 404 URL
        url = 'https://www.coingecko.com/en/search_v3?query=marblex'
        Gen(project_name, url).gen_loop()