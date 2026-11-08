import os
import time
import logging
import datetime
from utils.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Opensea alert')

def alert(data, duration):
    """
    热门NFT项目
    """
    collectionAddress = data['collectionAddress']
    url = f'https://pro.opensea.io/collection/{collectionAddress}'
    name = data.get('collectionName', '')
    try:
        mint_time_stamp = data['firstMintAt']
        firstMintAt = datetime.datetime.fromtimestamp(mint_time_stamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return
    totalMintCount = data.get('totalMintCount')
    floorPrice =  data.get('floorPrice')
    if not floorPrice:
        logger.info(f'{name} floorPrice 为空')
        return
    floorPrice = int(float(floorPrice)) / 1000000000000000000
    mintCount = data['mintCount']
    uniqueMintersPercentage = data.get('uniqueMintersPercentage')
    if not uniqueMintersPercentage:
        logger.info(f'{name} uniqueMintersPercentage 为空')
        return
    if mint_time_stamp < (int(time.time()) - 3*24*60*60):
        logger.info(f'{name} 不是最近3天的')
        return
    if not totalMintCount:
        logger.info(f'{name} totalMintCount 字段缺失')
        return
    if int(totalMintCount) <= 500:
        logger.info(f'{name} totalMintCount 小于500')
        return
    if floorPrice <= 0.002:
        logger.info(f'{name} floorPrice 小于 0.002')
        return
    if mintCount <= 50:
        logger.info(f'{name} mintCount 小于 50')
        return
    if uniqueMintersPercentage <= 10:
        logger.info(f'{name} uniqueMintersPercentage 小于 10%')
        return
    if duration != '1_hour':
        logger.info(f'{name} duration {duration}')
        return
    content = f"""
    name: {name}
    url: {url}
    mint开始时间: {firstMintAt}
    mint总数: {totalMintCount}
    地板价: {floorPrice}
    1h mint数量: {mintCount}
    唯一地址mint占比: {uniqueMintersPercentage}
    """
    webhook_api = os.getenv('LARK_WEBHOOK_OPENSEA', '')
    sender(content, webhook_api, 'NFT')
    return True

