from config import config
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('QQ Group Monitor')

def init_setting():
    device = config.DEVICE
    with open('other_spider/qqgroup/mirai_kotlin/device.json','w',encoding='utf-8')as f:
        f.write(device)
    logger.info(f'已经配置好设备ID：{device}')
    logger.info('waiting ......')
    time.sleep(3)

