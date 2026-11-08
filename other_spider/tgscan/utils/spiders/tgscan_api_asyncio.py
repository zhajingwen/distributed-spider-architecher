import json
import aiohttp
import os
import logging
from retry import retry
from other_spider.tgscan.utils.spiders.content_format import Format

env = os.environ.get('env')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TGscan API Spider Async')

class Spider:
    """
    异步
    请求群关系数据提供方接口
    """
    def __init__(self):
        if env == 'prod':
            self.search_url = 'https://api.tgdev.io/tgscan/v1/search'
            self.api_key = os.getenv('API_KEY_TGSCAN', '')
        else:
            self.search_url = 'https://api.tgdev.io/tgscan/v1/test/search'
            self.api_key = os.getenv('API_KEY_TGSCAN_2', '')
        self.check_username_url = 'https://api.tgdev.io/tgscan/v1/user/check'
        self.balance_url = 'https://api.tgdev.io/tgscan/v1/balance'
        # 余额报警阈值
        self.balance_alert_threshold = 10000

    @retry(tries=3)
    async def req(self, user_name, url, headers):
        """
        发起 api请求
        """
        if user_name:
            user_name = user_name.replace('@', '')
            params = {
                'query':user_name
            }
        else:
            params = None
        logger.info(f'post: {url}')
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=params) as res:
                logger.info(f'response {res.status}: {url}')
                content = await res.text()
                data = json.loads(content)
                # 无法用下面的方法来直接解析成字典，会报错，但是找不到具体原因是为啥
                # data = await res.json()
                status = data['status']
                if status != 'ok':
                    message = data['result'].get('message','未知因素')
                    logger.error(f'查询失败: {message}')
                    return
                else:
                    return data

    async def check_user_exsits(self, user_name):
        """
        检测用户是否存在，检测是否有群
        该方法只支持生产环境的 api_key
        return False, 0, 1, 2   (只有2才会执行search操作)
        """
        api_key = os.getenv('API_KEY_TGSCAN', '')
        headers = {
            'Api-Key': api_key
        }
        data = await self.req(user_name, self.check_username_url, headers)
        if data:
            result = data['result']
            # 查询不到用户时，才会存在这个key
            if 'message' in result:
                # 表示用户的username错误
                return 0
            else:
                known_num_groups = result['meta']['known_num_groups']
                if known_num_groups == 0:
                    # 未加入任何群
                    return 1
                else:
                    # 加入了群
                    return 2
        # 没有该用户
        else:
            return False

    async def search_user(self, user_name):
        """
        通过username查询群关系
        return: list or None
        """
        headers = {
            'Api-Key': self.api_key
        }
        data = await self.req(user_name, self.search_url, headers)
        if data:
            content_list = Format().format(data)
            return content_list
        else:
            return

    async def search(self, user_name):
        """
        1、先进性校验用户名合法性
        2、合法则进行 username 查询接口调用，并返回结果；否则返回None
        return: list or None
        """
        search_result = None
        check = await self.check_user_exsits(user_name)
        if check == False:
            logger.error(f'check 用户名错误：{user_name}')
        elif check == 0:
            logger.error(f'check 用户名错误：{user_name}')
        elif check == 1:
            logger.error(f'check 该用户未加入任何群：{user_name}')
        elif check == 2:
            search_result = await self.search_user(user_name)
        else:
            logger.error(f'check 用户校验发生未知错误：{user_name}')
        logger.info(f'搜索结果：{search_result}')
        return search_result

    async def check_balance_alert(self):
        """
        获取 tgdev 账户余额，当小于阈值的时候，return True
        return: False or True(需要告警) or int(需要告警)
        """
        api_key = os.getenv('API_KEY_TGSCAN', '')
        headers = {
            'Api-Key': api_key
        }
        data = await self.req(None, self.balance_url, headers)
        if data:
            # int
            num_credits = data['result']['num_credits']
            if num_credits < self.balance_alert_threshold:
                logger.info(f'tgdev余额紧张：{num_credits} credits')
                return num_credits
            else:
                logger.info(f'tgdev余额：{num_credits} credits')
                return False
        else:
            logger.info('tgdev余额查询失败！')
            return True
