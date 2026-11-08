import logging
import time
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, ForceReply,InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from hashlib import md5
from other_spider.tgscan.utils.redisdb import redis_cli
from other_spider.tgscan.utils.config.config import Deduct_fee_num
from other_spider.tgscan.utils.spiders.tgscan_api_asyncio import Spider
from other_spider.tgscan.utils.block_chain.search_balance import balance_search
from other_spider.tgscan.utils.even_type.balance_manage import BalanceManage
from other_spider.tgscan.utils.even_type.referral_program import ReferralProgram

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Handler Base')

class BaseHandler:
    def __init__(self, username):
        # self.bot_token = "<TG_BOT_TOKEN_TEST>"
        self.redis_cli = redis_cli()
        # self.username = username
        # 存放图片ID
        self.exchange_fee_demo_key = f'tgscan:exchange_fee_demo_key:{username}'
        self.username_demo_key = f'tgscan:username_demo:{username}'
        # 防止短时间内误操作和洪水攻击
        self.filter_key_base = 'tgscan:filter:{}'
        # 存储用户username:余额的 hash
        # username作为key
        self.users_balance_key = 'tgscan:users:balance'
        # set结构，存放所有钱包地址
        self.wallets_address = 'tgscan:wallets'
        # hash 结构，钱包地址回收任务库
        self.wallets_address_sc = 'tgscan:wallets:sc'
        # 路由ID
        self.CHOOSING, \
        self.TYPING_VALUE, \
        self.TARGET_USER_ID, \
        self.CHARGE_AMOUNT, \
        self.CHARGED_DONE, \
        self.BALANCE_RE_CONFIRM = range(6)

        reply_keyboard_cs = [
            ["查群关系", "充值"],
        ]
        self.markup_cs = ReplyKeyboardMarkup(
            reply_keyboard_cs,
            # one_time_keyboard=True,
            # 调整为合理大小
            resize_keyboard=True,
            # 常驻
            is_persistent=True
            # input_field_placeholder = "请输入目标用户ID，比如：@mayun"
        )
        reply_keyboard_confirm = [
            ["取消充值", "充值完成"],
        ]
        self.markup_confirm = ReplyKeyboardMarkup(
            reply_keyboard_confirm,
            # 用户点击后就让其取消
            # one_time_keyboard=True,
            # 调整按钮格式
            resize_keyboard=True,
            # 如果不定住，用户误点击输入框，该键盘就会消失了
            is_persistent=True
            # input_field_placeholder = "请输入目标用户ID，比如：@mayun"
        )
        # 加值相关的操作
        self.balance_manage = BalanceManage()
        # 传销相关操作
        self.referral_program = ReferralProgram()
        self.fallbacks = [
            # MessageHandler(filters.Regex("^xxx"), self.charge_learning),
            CallbackQueryHandler(self.charge_learning, pattern='USDT')
        ]
        # 扣费金额
        self.Deduct_fee_num = Deduct_fee_num

    async def message_pass(self, update, samemessage_ex: int, sameuser_ex: int):
        """
        防止短时间误点击的高频发送，
        防止浑水攻击
        能放行的返回 True
        """
        text = update.message.text
        user = update.effective_user
        user_id = user.id
        # 一个用户同一条消息10s内只能发送一次
        filter_content = f'{user_id}{text}'
        uid = md5(filter_content.encode()).hexdigest()
        key = self.filter_key_base.format(uid)
        status = self.redis_cli.get(key)
        if status:
            logger.warning(f'洪水：{user.username} {text}')
            return
        else:
            self.redis_cli.setex(key,samemessage_ex,1)
        # 同一个用户不能再1s内连续发送任何消息
        # 如果超过频率 用户会被短暂"静默"（用户不知情）拉黑，拉黑时长由 sameuser_ex 决定
        key_userid = self.filter_key_base.format(user_id)
        status_userid = self.redis_cli.get(key_userid)
        if status_userid:
            logger.warning(f'洪水：{user.username} {text}')
            return
        else:
            self.redis_cli.setex(key_userid,sameuser_ex,1)
        # 能放行则返回True
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        处理 /start 命令
        """
        # 同一消息20s只能发送一次 同一用户2s只能发送一条消息
        pass_status = await self.message_pass(update, 20, 2)
        # 能通过攻击校验的才处理
        if pass_status:
            # 新用户相关操作
            await self.balance_manage.new_user_bonus(update, context)
            user = update.effective_user
            user_balance = await self.balance_manage.get_user_balance(user.id)
            # 通知频道的爬名称
            channelname = 'grouprelation'
            # /start 指令给用户发送通知频道超链接
            channel_content = f'<a href="https://t.me/{channelname}"><b> 👉📢通知频道👈</b></a>\n\n'
            id_content = f'<b>ID: </b>{user.id}\n'
            await update.message.reply_html(
                f"{channel_content}{id_content}<b>账户余额：{user_balance}</b> U\n👇<b>请通过下方键盘按钮提交您的请求</b>👇",
                reply_markup=self.markup_cs,
                disable_web_page_preview=True
            )
            return self.CHOOSING

    async def charge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        充值入口，提醒用户输入充值金额
        """
        # 30s 只需发充值指令一次 ，用户发送任何消息限制为2s 1次
        pass_status = await self.message_pass(update, 30, 2)
        if not pass_status:
            return
        # 解释充值方式
        keyboard = [[InlineKeyboardButton("什么是USDT？", callback_data='USDT')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(
            "<b>充值方式：</b>区块链\n"
            "<b>通道：</b>任意钱包或交易所\n"
            "<b>接受的币种：</b>USDT\n"
            "<b>网络：</b>BEP20(Binace Smart Chain)\n"
            "<b>充值门槛：</b>无门槛，任意金额 0 ~ +∞\n"
            "<b>注意：</b>如果您从交易所充值U，交易所会可能扣手续费，充值到账金额为扣掉手续费后的金额",
            reply_markup=reply_markup
        )
        # 示例图片的路径
        path = 'other_spider/tgscan/utils/photos/exchange_fee_demo.jpg'
        caption = '<b>交易所样例</b>\n\n<b>1、请注意左下角的手续费扣费信息</b>\n' \
                  '<b>2、在提现地址输入充值地址</b>（交易所是以提币（提现）的方式充值）\n' \
                  '<b>3、点击 <i>提现</i> 即可完成充值</b>'
        old_file_id = self.redis_cli.get(self.exchange_fee_demo_key)
        # 首次交互的图片需要从本地文件读取
        if not old_file_id:
            logger.info(f'原始图片open 发送')
            # 发送交易所充值图片示例
            with open(path, 'rb') as photo:
                # `@mayun`必须得加``否则会被解析成用户超链接
                message = await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode='html',
                )
                file_id = message.photo[-1].file_id
                self.redis_cli.set(self.exchange_fee_demo_key,file_id)
                logger.info(f'交易所费用样例图ID已存入redis: {file_id}')
        # 以后直接从redis拿到图片ID（该图片已经存在于TG服务器）发送
        else:
            logger.info(f'用图片缓存发送: {old_file_id}')
            # `@mayun`必须得加``否则会被解析成用户超链接
            await update.message.reply_photo(
                photo=old_file_id,
                caption=caption,
                parse_mode='html',
            )
        await update.message.reply_html(
            "<b>请输入充值金额：</b>\n"
            "比如 0.1 （表示充值 <b>0.1</b> USDT）",
            reply_markup=ForceReply(input_field_placeholder='输入充值金额')
        )
        return self.CHARGE_AMOUNT

    async def charge_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理用户输入的充值金额
        """
        # 处理用户输入的原始文本
        origin_user_input_charge_amount = update.message.text.replace('usdt','').replace('USDT','')
        origin_user_input_charge_amount = origin_user_input_charge_amount.replace('u','').replace('U','')
        # 格式化用户输入的充值金额
        user_input_charge_amount = origin_user_input_charge_amount.strip()
        user = update.effective_user
        try:
            float(user_input_charge_amount)
        except:
            logger.info(f'{user.username} 充值金额非法：{user_input_charge_amount}')
            await update.message.reply_html(
                f"<b>消息非法</b>\n"
                "👇 请重新输入 👇",
                reply_markup=ForceReply(input_field_placeholder='输入充值金额')
            )
            return self.CHARGE_AMOUNT
        logger.info(f'用户：{user.username} 充值：{user_input_charge_amount}')
        # 绑定用户充值的目标金额
        context.user_data["charge"] = user_input_charge_amount
        await update.message.reply_html(
            f"<b>您将充值：</b>{user_input_charge_amount} USDT\n"
            "👇 <b>请复制下面的充值地址完成充值</b> 👇\n",
            reply_markup = self.markup_confirm

        )
        wallet_address = await self.balance_manage.pop_wallet_address(update, context)
        # 当没有可分配的钱包地址时，结束当前的会话线程
        if not wallet_address:
            return ConversationHandler.END
        # 地址被分配时的时间戳
        wallet_address_time = int(time.time())
        # 提交任务给钱包地址回收线程智能处理
        self.redis_cli.hset(self.wallets_address_sc, wallet_address, wallet_address_time)
        # 钱包地址
        await update.message.reply_text(wallet_address)
        await update.message.reply_html("<b>提醒：</b>在30分钟内完成充值，充值完成后点击屏幕最下方的 <b><i>充值完成</i></b> 按钮\n")
        # 将用户充值前的余额绑定到用户状态
        logger.info(f'开始查询用户 {user.username} 充值前的余额')
        balance = await balance_search(wallet_address)
        user_data = context.user_data
        # 充值前的钱包余额
        user_data['wallet_balance_before_charge'] = balance
        # 绑定当前分配给用户的地址
        user_data['wallet_address'] = wallet_address
        # 绑定地址分配给用户时的时间戳
        user_data['wallet_address_time'] = wallet_address_time
        # logger.info(f'用户 {user.username} 分配钱包地址：{wallet_address}')
        logger.info(f'用户 {user.username} 分配的钱包地址：{wallet_address} 充值前余额：{balance} U')
        return self.CHARGED_DONE

    async def charged_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        "充值完成" 按钮 事件处理
        """
        user_data = context.user_data
        user = update.effective_user
        wallet_address = user_data['wallet_address']
        # 如果用户超过30m未点击"充值完成按钮"，钱包会被回收，此时结束整个会话线程
        # 不存在，就说明被回收了
        wallet_address_exsit_status = self.redis_cli.hget(self.wallets_address_sc, wallet_address)
        if not wallet_address_exsit_status:
            await update.message.reply_html(
                "已<b>超时</b>，充值失败！",
                # 回到首页
                reply_markup=self.markup_cs
            )
            user_data.clear()
            return ConversationHandler.END

        wallet_balance_before_charge = user_data['wallet_balance_before_charge']
        logger.info(f'开始查询用户 {user.username} wallet {wallet_address} 充值后的余额')
        balance_now = await balance_search(wallet_address)
        # 生成充值订单号 并绑定到用户态
        charge_order_id = md5(f'{user.username}{int(time.time())}'.encode()).hexdigest()
        user_data['charge_order_id'] = charge_order_id
        charge_balance = float(balance_now - wallet_balance_before_charge)
        logger.info(
            f'用户 {user.username} 充值订单号： {charge_order_id} '
            f'钱包：{wallet_address} 充值到账： {charge_balance} 已分配钱包余额: {balance_now}'
        )
        # logger.info(f'用户 {user.username} 充值到账： {charge_balance}')
        # 查询到的 到账金额 绑定到用户态
        user_data['charge_balance'] = charge_balance
        # 剔除原有键盘
        await update.message.reply_text(f'订单号：{charge_order_id}', reply_markup=ReplyKeyboardRemove())
        # 如果充值未到账，提醒用户待会再查询到账状态
        if charge_balance == 0:
            user_data['refresh_charge_status_num'] = 1
            # 创建一个具有两个按钮的内联键盘
            keyboard = [
                [
                    InlineKeyboardButton("刷新", callback_data='1'),
                    InlineKeyboardButton("取消充值", callback_data='2'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # {charge_order_id}
            await update.message.reply_html(
                f'<b>尚未到账</b>，请确认链上交易已完成，并<b>刷新</b>到账状态',
                reply_markup=reply_markup
            )
            return self.BALANCE_RE_CONFIRM
        # 充值到账后的交互
        else:
            result = await self.balance_manage.charge_success(update, context)
            # 结束所有会话
            return result

    async def charged_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        取消充值 事件处理
        同时支持自定义键盘和内联按钮
        """
        # 回收钱包地址
        await self.balance_manage.wallet_address_sc_of_message_function(update, context)
        content = '取消成功'
        user_data = context.user_data
        # 判断是否是内联按钮
        query = update.callback_query
        if query:
            # 确认按钮单击
            await query.answer()
            # 剔除嵌入内联按钮的消息
            await query.delete_message()
            # 给用户响应
            await query.message.reply_text(
                content,
                # 弹出充值 查询群关系按钮
                reply_markup=self.markup_cs
            )
        # 键盘按钮
        else:
            await update.message.reply_text(
                content,
                # 弹出充值 查询群关系按钮
                reply_markup=self.markup_cs
            )
        user = update.effective_user
        logger.info(f'主动取消充值，user: {user.username}')
        # 清空  context.user_data 字典
        user_data.clear()
        return ConversationHandler.END

    async def hold_on_user_typing_target_userID(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理'查群关系'按钮事件
        弹出输入框等待用户输入 ---> 查询某目标背后的群关系
        """
        # 3s内只容许发 "查询群关系"指令 1次；发送任何消息限制频率 2s 1次
        pass_status = await self.message_pass(update, 3, 2)
        # 洪水攻击验证不通过
        if not pass_status:
            return
        user = update.effective_user
        # 看用户钱够不够扣的
        user_balance = await self.balance_manage.get_user_balance(user.id)
        # user_balance = float(user_balance)
        # 不够的处理 并 跳出
        if user_balance < abs(self.Deduct_fee_num):
            # 邀请奖励按钮
            referral_button = await self.referral_program.gen_invite_button(update, context)
            await update.message.reply_html(
                f"💰：<b>{user_balance}</b> U 已不足，请👉🏻充值",
                reply_markup=referral_button
            )
            # 结束会话线程
            return ConversationHandler.END
        old_file_id = self.redis_cli.get(self.username_demo_key)
        search_caption_notice = '*请输入需要查询的用户ID：*\n*比如：* `zxcv1231231` 或 `@zxcv1231231`'
        # 首次发送图片
        if not old_file_id:
            logger.info(f'原始图片open 发送')
            # 示例图片的路径
            path = 'other_spider/tgscan/utils/photos/username_demo.png'
            # 发送图片示例
            with open(path, 'rb') as photo:
                message = await update.message.reply_photo(
                    photo=photo,
                    caption=search_caption_notice,
                    parse_mode='MarkdownV2',
                    # input_field_placeholder 字符不能过长，过长就不显示了
                    reply_markup=ForceReply(input_field_placeholder='输入目标用户ID'),
                )
                file_id = message.photo[-1].file_id
                self.redis_cli.set(self.username_demo_key,file_id)
                logger.info(f'用户ID样例图ID已存入redis: {file_id}')
        else:
            logger.info(f'用图片缓存发送: {old_file_id}')
            # `@mayun`必须得加``否则会被解析成用户超链接
            await update.message.reply_photo(
                photo=old_file_id,
                caption=search_caption_notice,
                parse_mode='MarkdownV2',
                reply_markup=ForceReply(input_field_placeholder='输入目标用户ID'),
            )

        # 路由到TYPING_CHOICE handler
        return self.TARGET_USER_ID

    async def search_ID(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        输入的username处理，搜索目标用户ID
        该方法耗时处理 会阻塞新用户消息的处理
        无论成功与否都路由到用户按钮选择handler
        """
        # 防止网络问题，导致一条消息被推送多次（3s内只处理相同消息1次）；发送任何消息限制频率 2s 1次
        pass_status = await self.message_pass(update, 3, 2)
        # 洪水攻击验证不通过  返回None将继续停留在该状态处理函数
        if not pass_status:
            return

        start_time = int(time.time())
        text = update.message.text
        # 异步防止阻塞 list
        result = await Spider().search(text)
        if not result:
            await update.message.reply_html(
                f"查询失败，无该用户的信息：<b>{text}</b>",
                reply_markup=self.markup_cs,
            )
        else:
            # 由于查询到的数据可能非常长，而TG对于消息的长度有控制，故这里做切片处理
            for content in result:
                # 群名中的某些特殊字符可能会导致失败
                try:
                    await update.message.reply_html(
                        content,
                        reply_markup=self.markup_cs,
                    )
                except:
                    await update.message.reply_text(
                        content,
                        reply_markup=self.markup_cs,
                    )
        # 执行扣费 并 发送余额通知（如果余额不足会提醒充值）
        user_data = context.user_data
        user_data['Deduct_fee_num'] = self.Deduct_fee_num
        await self.balance_manage.deduct(update, context)

        time_spended = f'耗时：{time.time()-start_time}'
        logger.info(time_spended)
        logger.info(f'message reply_to_message: {update.message.reply_to_message}')
        return ConversationHandler.END

    async def charge_learning(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        充值方式视频介绍
        """
        query = update.callback_query
        # 确认按钮单击
        await query.answer()
        # 处理回调数据
        if query.data == 'USDT':
            url = 'https://youtu.be/vDE1Utw1ZVw?si=6yOsTfXjhz2JlMqX'
            # 邀请注册按钮
            keyboard = [
                [
                    InlineKeyboardButton("👉观看👈", url=url),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "USDT基本介绍",
                reply_markup=reply_markup,
            )
            await query.message.reply_html(
                "如需进一步了解，请自行 <b>Google</b>"
            )

    def state(self):
        """
        所有路由函数路由解析关系
        """
        # 键盘路由函数列表
        keyboard_handler = [
            MessageHandler(filters.Regex("^充值$"), self.charge),
            MessageHandler(filters.Regex("^查群关系$"), self.hold_on_user_typing_target_userID)
        ]
        state = {
                # 处理键盘点击事件
                self.CHOOSING: keyboard_handler,
                # [查询群关系] 处理需要查询的目标用户ID
                self.TARGET_USER_ID: [
                    MessageHandler(
                        # 匹配所有的文本消息，但是不是命令消息和文本不为"Done"的消息
                        filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$") | filters.Regex("^查群关系$")),
                        self.search_ID
                    ),
                ],
                # [充值] 处理用户输入的充值金额
                self.CHARGE_AMOUNT: [
                    MessageHandler(
                        # 匹配所有的文本消息，但是不是命令消息和文本不为"Done"的消息
                        # 由于网络问题，用户会连续点击点击两次充值，那么第二次点击会被认为是回复 self.charge 的，那么需要兼容这种异常
                        filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$") | filters.Regex("^充值$")),
                        self.charge_amount
                    ),
                ],
                # [充值] 充值用户点击充值装填按钮
                #    完成按钮后，执行校验程序，给用户数据库加充值金额，响应客户充值已到账
                # 取消充值按钮，给客户响应 取消成功
                self.CHARGED_DONE: [
                    MessageHandler(filters.Regex("^充值完成$"), self.charged_done),
                    MessageHandler(filters.Regex("^取消充值$"), self.charged_cancel),
                ],
                # 用户充值到账状态 刷新 + 取消充值  内联按钮 处理函数
                self.BALANCE_RE_CONFIRM: [
                    CallbackQueryHandler(self.balance_manage.user_charge_status_refresh, pattern='1'),
                    CallbackQueryHandler(self.charged_cancel, pattern='2')
                ]
            }
        return state

    def main(self):
        conv_handler = ConversationHandler(
            # entry_points=keyboard_handler,
            # start 命令激活入口
            entry_points=[CommandHandler("start", self.start)],
            # entry_points=[cmd_handler],
            # entry_points=keyboard_handler,
            states=self.state(),
            fallbacks=self.fallbacks
        )
        return conv_handler