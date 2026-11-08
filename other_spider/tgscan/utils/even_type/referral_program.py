import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from other_spider.tgscan.utils.config.config import referral_bonus

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Handler Base')

class ReferralProgram:
    def __init__(self):
        # 推荐奖励额度
        self.referral_bonus = referral_bonus

    async def gen_invite_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        生成邀请按钮（内联按钮）
        """
        user_id = update.effective_user.id
        # @your_test_bot
        bot_username = context.bot.username
        invite_link = f'https://t.me/{bot_username}?start={user_id}&text=群关系机器人，免费使用！'
        deep_link = f"https://t.me/share/url?url={invite_link}"  # 生成包含 Deep Linking 的邀请链接
        # 邀请注册按钮
        keyboard = [
            [
                InlineKeyboardButton(f"👉邀请新用户，奖励{self.referral_bonus}U /人👈", url=deep_link),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return reply_markup

    async def invite_parent_send_notice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        给邀请发起人发送消息（当成功邀请用户后）+ 奖励发放
        不能自己邀请自己
        """
        user = update.effective_user
        # int
        # userid = user.id
        # list 如果没有邀请来源是空列表[]，有的话会有一个元素比如：['2011448716']
        inviter_user_id = context.args
        # 存在邀请关系
        if inviter_user_id:
            # 提取邀请发起人的ID (str)
            inviter_user_id = inviter_user_id[0]
            # 防止自己邀请自己
            if int(inviter_user_id) != user.id:
                # 给邀请人发送通知
                await context.bot.send_message(
                    chat_id=inviter_user_id,
                    text=f"🎉邀请 1 人，奖励 <b>{self.referral_bonus}</b> U",
                    parse_mode='html'
                )
