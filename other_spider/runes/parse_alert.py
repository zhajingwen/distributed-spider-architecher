import datetime
import logging
import os
from utils.redisdb import redis_cli
from other_spider.cmc.bot.lark_bot import sender

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Parse runes')
env = os.environ.get('env')

class Parse:
    def __init__(self):
        self.redis_cli = redis_cli()
        self.lark_url = os.getenv('LARK_WEBHOOK_GENIIDATA', '')
        self.black_list = 'runes:alert:blacklist'

    def parse(self, data):
        """
        解析数据
        """
        data = data['data']
        detail = data['detail']
        for item in detail:
            name = item['rune']
            holdersCount = item['holders']
            if holdersCount < 50:
                continue
            deployBlocktime = item['timestamp']
            dt_object = datetime.datetime.fromtimestamp(deployBlocktime)
            deploy_date = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            supply = int(item['supply'])
            if 'terms' in item:
                terms = item['terms']
                amount = int(terms['amount'])
                cap = int(terms['cap'])
                process = round((supply/(amount*cap))*100, 3)
                if process < 5:
                    continue
                transactions = item['transactions']
                minting = amount*cap - supply
                process_content = f'{supply}/{amount*cap}'

                content = f"""name: {name}
                    holdersCount: {holdersCount}
                    deploy_date: {deploy_date}  
                    process: {process}                  
                    transactions: {transactions}     
                    正在mint：{minting}             
                    Progress：{process_content}                   
                    """
                self.alert(content, name)

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
