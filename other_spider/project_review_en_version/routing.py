import logging
import time
from .spiders.dextools_spider import Dextools
from .spiders.cmc_spider import Cmc
from .spiders.coingecko_spider import Coingecko
from utils.redisdb import redis_cli
from .rich_information.combined_info import combined_information

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review Parse Url')

class Route:
    """
    解析用户输入的链接
    路由到不同的处理模块
    """
    def __init__(self):
        # 所有进来的URL都得先看该队列是否有任务
        self.dextools_jobs = 'project_review_en_version:dextools:jobs'
        self.redis_cli = redis_cli()

    def listen(self):
        """
        监听redis队列的任务，并对任务进行处理
        """
        start_time = int(time.time())
        data = None
        # 监听队列任务
        while True:
            if int(time.time()) - start_time > 60:
                logger.error('未监听到有任务！')
                break
            address = self.redis_cli.spop(self.dextools_jobs)
            if address:
                logger.info(f'redis队列监听到任务：{address}')
                data = Dextools().coin_info_polymeric(address)
                break
        if not data:
            logger.error('dextools无法处理任务')
        return data

    def dextools(self, url):
        result = Dextools().run_url(url)
        return result

    def cmc(self, url):
        """
        解析地址并生成任务塞入redis让dextools爬虫来处理
        """
        # 解析出token地址塞入redis给dextools爬虫处理
        status = Cmc().run(url)
        if status:
            data = self.listen()
            return data
        else:
            return '该币无合约地址，无法提供数据聚合服务'

    def coingecko(self, url):
        """
        第二批次开通
        """
        # 解析出token address 塞入redis队列
        Coingecko().run(url)
        data = self.listen()
        return data

    def dexscreener(self, url):
        """
        第二批次开通
        """
        return 'dexscreener 暂未开通'

    def address(self, message_cmd):
        """
        当输入的消息是合约地址时也支持
        """
        result = Dextools().run_address(message_cmd)
        return result

    def deal_with(self, message_cmd):
        """
        解析请求，做匹配，识别是哪个站点
        """
        if 'dextools' in message_cmd:
            result = self.dextools(message_cmd)
            return result
        elif 'coinmarketcap' in message_cmd:
            result = self.cmc(message_cmd)
            return result
        elif 'coingecko' in message_cmd:
            result = self.coingecko(message_cmd)
            return result
        elif 'dexscreener' in message_cmd:
            result = self.dexscreener(message_cmd)
            return result
        else:
            if len(message_cmd) == 42:
                result = self.address(message_cmd)
                return result
            else:
                logger.error('输入的链接错误，请重新输入！')
                return

    def conversation_format(self, data):
        """转换格式"""
        if not isinstance(data, dict):
            return
        base_info = data['base_info']
        base_info_content = '基础信息：\n'
        chain_data = data['chain_data']
        chain_data_content = '链上数据：\n'
        social = data['social']
        social_content = '社媒：\n'
        link = data['link']
        link_content = '相关链接：\n'
        for key, value in base_info.items():
            row = f'{key}: {value}\n'
            base_info_content += row
        for key, value in chain_data.items():
            row = f'{key}: {value}\n'
            chain_data_content += row
        for key, value in social.items():
            row = f'{key}: {value}\n'
            social_content += row
        for key, value in link.items():
            row = f'{key}: {value}\n'
            link_content += row
        content = f'{base_info_content}\n{chain_data_content}\n{social_content}\n{link_content}'
        return content

    def combined_information(self, message_cmd):
        """
        丰富信息维度
        包括：cex volume，website visiters, twitter粉丝量, discord人数
        return: None or string
        """
        # dicr or string
        data = self.deal_with(message_cmd)
        if data:
            if isinstance(data, dict):
                # 丰富信息维度
                data = combined_information(data)
                content = self.conversation_format(data)
            else:
                content = data
            return content
        else:
            return