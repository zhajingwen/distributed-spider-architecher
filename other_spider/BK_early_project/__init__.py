import logging
from .event_handle import app
from .ips.to_redis import IpStore
from .cookies.gen_cookies import Gen

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BK Early Project')

def run(spider_name):
    if spider_name == 'run':
        # web server
        app.run(host='0.0.0.0', port=84)
    elif spider_name == 'ipmonitor':
        IpStore().ipstore_monitor()
    elif spider_name == 'gencookies':
        Gen().gen_loop()