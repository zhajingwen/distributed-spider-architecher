from telegram import Update
from telegram.ext import Application
from threading import Thread
from other_spider.tgscan.utils.handlers.keyboard_handler import KeyboardHandler
from other_spider.tgscan.utils.handlers.start_comand_handler import StartHandler
from other_spider.tgscan.utils.even_type.balance_manage import BalanceManage

class TGBotRegister:
    """
    单个机器人的事件监听注册
    """
    def __init__(self, username):
        self.keyboar_handler = KeyboardHandler(username).main()
        self.start_handler = StartHandler(username).main()
        # 加值相关的操作
        self.balance_manage = BalanceManage()

    async def error(self, update, context):
        """
        捕获异常：telegram.error.NetworkError: httpx.RemoteProtocolError: Server disconnected without sending a response.
        """
        print(f'连接异常： {context.error}')

    def main(self, token) -> None:
        # 载入所有钱包地址
        self.balance_manage.insert_wallets_address_to_redis()
        # 钱包地址回收的独立线程 （异步）
        t = Thread(target=self.balance_manage.wallet_address_source_collection)
        t.start()
        # 默认0.5s请求一次 https://api.telegram.org/bot<TG_BOT_TOKEN_TEST>/getUpdates  来获取最新的消息推送
        # 实现方式long polling  run_polling方法  这种方法会建立一个持久的连接并等待服务器发送更新
        application = Application.builder().token(token).build()
        application.add_handler(self.start_handler)
        application.add_handler(self.keyboar_handler)
        # 为了解决在开发环境中总是报如下错误：
        # telegram.error.NetworkError: httpx.RemoteProtocolError: Server disconnected without sending a response.
        application.add_error_handler(self.error)
        # run_polling 经过测试，不具备并发处理能力，A用户的消息会阻塞B用户的消息
        application.run_polling(allowed_updates=Update.ALL_TYPES, timeout=600)
