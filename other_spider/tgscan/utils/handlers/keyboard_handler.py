from .base import BaseHandler
import logging
from typing import Dict
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, ForceReply
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, ForceReply,InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (
    # Application,
    # CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
# from .tgscan_api import Spider


class KeyboardHandler(BaseHandler):
    """
    内联键盘 + 自定义键盘 作为entries
    """
    def __init__(self, username):
        super().__init__(username)
        # self.arg2 = arg2
    #
    # async def charge_learning(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """
    #     充值方式视频介绍
    #     """
    #     query = update.callback_query
    #     # 确认按钮单击
    #     await query.answer()
    #     # 处理回调数据
    #     if query.data == 'USDT':
    #         url = 'https://youtu.be/vDE1Utw1ZVw?si=6yOsTfXjhz2JlMqX'
    #         # 邀请注册按钮
    #         keyboard = [
    #             [
    #                 InlineKeyboardButton("👉观看👈", url=url),
    #             ]
    #         ]
    #         reply_markup = InlineKeyboardMarkup(keyboard)
    #         await query.message.reply_text(
    #             "USDT基本介绍",
    #             reply_markup=reply_markup,
    #         )
    #         await query.message.reply_html(
    #             "如需进一步了解，请自行 <b>Google</b>"
    #         )
    #

    # 重写handler
    def main(self):

        # 键盘路由函数列表
        keyboard_handler = [
            # 自定义键盘
            MessageHandler(filters.Regex("^充值$"), self.charge),
            MessageHandler(filters.Regex("^查群关系$"), self.hold_on_user_typing_target_userID),
            # 内联键盘
            CallbackQueryHandler(self.charge_learning, pattern='USDT')
        ]
        conv_handler = ConversationHandler(
            # 键盘按钮 激活入口
            entry_points=keyboard_handler,
            states=self.state(),
            # fallbacks=[MessageHandler(filters.Regex("^Done$"), self.done)],
            # fallbacks=[MessageHandler(filters.Regex("^充值方式科普$"), self.charge_learning)],
            fallbacks=self.fallbacks
            # fallbacks=
        )
        return conv_handler