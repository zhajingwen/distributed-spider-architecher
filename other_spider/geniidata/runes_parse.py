import os
import logging
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Geniidata Gas')

class ParseRunes:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.lark_url = os.getenv('LARK_WEBHOOK_GENIIDATA', '')
        self.black_list = 'runes:alert:blacklist'

    def alert(self, content, name):
        """
        告警
        """
        if self.redis_cli.sismember(self.black_list, name):
            logger.info(f'告警过了：{name}')
            return
        sender(content, self.lark_url, name)
        # 报警后加入去重队列
        self.redis_cli.sadd(self.black_list,name)

    def parse(self, data):
        logger.info(f'Runes收到任务：{data}')
        data = data['data']
        rows = data['rows']
        minted = data['minted']
        for row in rows:
            # 通过该ID可进行关联
            inscriptionId = row['inscriptionId']
            name = row['tick']
            item = minted.get(inscriptionId)
            if not item:
                logger.error(f'无法匹配到对应的项目：{inscriptionId}')
                continue
            cap = item['cap']
            mints = item['mints']
            holdersCount = item['holders']
            process_percent = round((mints/float(cap))*100,2)
            memPoolMints = item['memPoolMints']
            progress_content = f'{mints}/{cap}'
            content = f"""name: {name}
                holdersCount: {holdersCount}
                deploy_date: 来自geniidata无该数据
                process: {process_percent}%                  
                transactions: 来自geniidata无该数据 
                正在mint：{memPoolMints}             
                Progress：{progress_content}      
                in memory pool: {memPoolMints}            
                """
            self.alert(content, name)

