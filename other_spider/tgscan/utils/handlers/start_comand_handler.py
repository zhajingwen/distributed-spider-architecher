from .base import BaseHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, ForceReply
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)


class StartHandler(BaseHandler):
    def __init__(self, username):
        super().__init__(username)

    async def support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理指令：/support，发送客服联系方式
        """
        # 同一消息60s只能发送一次 同一用户2s只能发送一条消息
        pass_status = await self.message_pass(update, 60, 2)
        # 能通过攻击校验的才处理
        if pass_status:
            support_nanme = 'laoguanjia'
            content = f'<a href="https://t.me/{support_nanme}"><b> 👉联系客服👈</b></a>'
            await update.message.reply_html(
                content
            )
            return ConversationHandler.END

    async def announce(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理指令：/announce，发送通知频道
        """
        # 同一消息60s只能发送一次 同一用户2s只能发送一条消息
        pass_status = await self.message_pass(update, 60, 2)
        # 能通过攻击校验的才处理
        if pass_status:
            announce_channel = 'grouprelation'
            content = f'<a href="https://t.me/{announce_channel}"><b> 👉加入通知频道👈</b></a>'
            await update.message.reply_html(
                content
            )
            return ConversationHandler.END

    def main(self):
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CommandHandler("support", self.support),
                CommandHandler("announce", self.announce),
            ],
            # 可有可无，在实际运行中并不会出现被调用的情况
            states=self.state(),
            fallbacks=self.fallbacks
        )
        return conv_handler
