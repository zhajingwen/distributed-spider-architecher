import os
import logging
import time
from hashlib import md5
from telegram import ReplyKeyboardMarkup, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackContext
)
# from utils.redisdb import redis_cli
from other_spider.tgscan.utils.redisdb import redis_cli
from other_spider.tgscan.utils.alert_push import sender
from other_spider.tgscan.utils.config.config import addresses as all_wallets_addresses
from other_spider.tgscan.utils.block_chain.search_balance import balance_search
from other_spider.tgscan.utils.even_type.referral_program import ReferralProgram
from other_spider.tgscan.utils.spiders.tgscan_api_asyncio import Spider
from other_spider.tgscan.utils.config.config import referral_bonus, white_list_rediskey, new_real_user_bonus, new_fake_user_bonus

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Balance Manage')

class BalanceManage:
    def __init__(self):
        self.redis_cli = redis_cli()
        # 存储用户username:余额的 hash   username作为key
        self.users_balance_key = 'tgscan:users:balance'
        # 存放所有钱包地址  set结构
        self.wallets_address = 'tgscan:wallets'
        # 钱包回收任务仓库 hash 结构
        self.wallets_address_sc = 'tgscan:wallets:sc'
        # 防止短时间内误操作和洪水攻击
        self.filter_key_base = 'tgscan:filter:{}'
        # 白名单（有过充值行为的加入白名单）set
        self.white_list = white_list_rediskey
        self.feishu_webhook = os.getenv('LARK_WEBHOOK_FEISHU_ALERT', '')
        reply_keyboard_cs = [
            ["查群关系", "充值"],
        ]
        self.markup_cs = ReplyKeyboardMarkup(
            reply_keyboard_cs,
            # 调整为合理大小
            resize_keyboard=True,
            # 常驻
            is_persistent=True
        )
        # 传销模块
        self.referral_program = ReferralProgram()
        # tgdev 交互模块
        self.tgdev_api = Spider()
        # 推荐奖励额度
        self.referral_bonus = referral_bonus

    async def charge_modify_database(self, user_id, volume, call_type):
        """
        统一数据库加值入口
        user_id： int 用户ID
        volume：float 用户充值金额
        call_type: str 调用类型
        """
        self.redis_cli.hincrbyfloat(self.users_balance_key, user_id, volume)
        logger.info(f'数据库完成加值，类型：{call_type} user_id：{user_id}  {volume} U')

    async def get_user_balance(self, user_id):
        """
        查询用户余额
        """
        user_balance = self.redis_cli.hget(self.users_balance_key, user_id)
        user_balance = float(user_balance)
        return user_balance

    async def pop_wallet_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        从数据库随机弹出一个钱包地址
        """
        members = self.redis_cli.scard(self.wallets_address)
        if members:
            wallet_address = self.redis_cli.spop(self.wallets_address)
            logger.info(f'随机抽取钱包地址：{wallet_address} 剩余：{members-1}')
            return wallet_address
        else:
            content = "<b>充值通道拥挤!</b>\n请稍等片刻再试"
            # 拉起键盘菜单
            await update.message.reply_html(
                content,
                reply_markup=self.markup_cs
            )
            await sender(f'余数：{members}', self.feishu_webhook, '无可分配钱包地址')
            # if members == 0:
            #     await sender(f'余数：{members}',self.feishu_webhook, '钱包地址紧张')
            return

    def insert_wallets_address_to_redis(self):
        """
        机器人启动时，将所有可被分配的钱包地址载入redis
        """
        # 载入地址前清空Redis缓存，这样可以通过配置文件来完成更新，避免redis中缓存旧的地址
        count_of_wallets_in_redis = self.redis_cli.scard(self.wallets_address)
        if count_of_wallets_in_redis > 0:
            logger.warning(f'redis中存在钱包地址，准备清空')
            self.redis_cli.delete(self.wallets_address)
            logger.warning(f'redis中钱包地址已清空')
        address_count = len(all_wallets_addresses)
        with self.redis_cli.pipeline(transaction=False)as pipe:
            for address in all_wallets_addresses:
                pipe.sadd(self.wallets_address, address)
            pipe.execute()
        logger.info(f'所有地址载入完成，共：{address_count} 条')

    async def referrer_bonus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        给推荐人发送奖励（数据库加值）
        存在用户名，才发推荐奖励
        """
        inviter_user_id = context.args
        user = update.effective_user
        # 存在邀请关系
        if inviter_user_id:
            # 提取邀请发起人的ID (str)
            inviter_user_id = inviter_user_id[0]
            # 防止自己邀请自己
            if int(inviter_user_id) != user.id:
                # 被推荐的人存在用户名，才发推荐奖励
                username = user.username
                if username:
                    # 加值，邀请1人加值 self.referral_bonus U
                    await self.charge_modify_database(int(inviter_user_id), self.referral_bonus, '邀请奖励发放')
                    logger.info(f'奖励已经入库，推荐人：{inviter_user_id}')

    async def new_user_bonus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        如果是新用户执行对应的处理逻辑
        """
        # 判断是否是新用户
        user = update.effective_user
        username = user.username
        userid = user.id
        # 是否是新用户的状态，False表示不存在
        old_status =self.redis_cli.hexists(self.users_balance_key, userid)
        # 新用户的处理逻辑
        if not old_status:
            logger.info(f'新用户注册 username：{username} userid: {userid}')
            # 有用户名的才算是有效推荐
            if username:
                # 给推荐人发送奖励（数据库加值）
                await self.referrer_bonus(update, context)
                # 给推荐人发送通知
                await self.referral_program.invite_parent_send_notice(update, context)
            # 有用户名的注册才送0.1U
            if username:
                # 新用户注册送 0.1 U (有用户名)
                await self.charge_modify_database(userid, new_real_user_bonus, '新用户注册赠送')
                content = f"<b>注册成功!</b>\n🥳🥳🥳🥳🥳🥳\n赠送：<b>{new_real_user_bonus}</b> U\n" \
                          "资费：\n    1、查询失败：<b>0.02</b>U /次（<i><u>用户名错误或该用户未加入任何群</u></i>）" \
                          "\n    2、查询成功：<b>0.2</b>U /次（<i><u>返回目标用户已加入的所有群</u></i>）"
            else:
                # 新用户注册送 0 U
                await self.charge_modify_database(userid, new_fake_user_bonus, '新用户注册赠送')
                content = "<b>注册成功!</b>\n🥳🥳🥳🥳🥳🥳\n" \
                          "资费：\n    1、查询失败：<b>0.02</b>U /次（<i><u>用户名错误或该用户未加入任何群</u></i>）" \
                          "\n    2、查询成功：<b>0.2</b>U /次（<i><u>返回目标用户已加入的所有群</u></i>）"
            # 生成邀请按钮
            invite_buttuon = await self.referral_program.gen_invite_button(update, context)
            await update.message.reply_html(content, reply_markup=invite_buttuon)
            # 新用户注册告警
            if username:
                alert_content = f"https://t.me/{username}"
            else:
                alert_content = f"https://t.me/{userid}"
            await sender(alert_content, self.feishu_webhook, '新用户注册')

    async def charge_balance_chage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        充值加值
        数据库加值、有新的充值通知管理员、回收钱包地址、、
        执行前提：已经经过链上校验，确实到账
        """
        user_data = context.user_data
        # 获取用户实际充值到账额 float
        charge_balance = user_data['charge_balance']
        # 为了防止过于长的位数导致程序故障，这里限制为最长4位
        charge_balance = round(charge_balance, 4)
        user = update.effective_user
        # 1、数据库加值
        await self.charge_modify_database(user.id, charge_balance, '用户主动充值')
        # 2、有新的充值通知管理员
        charge_order_id = user_data['charge_order_id']
        wallet_address = user_data['wallet_address']
        content = f'订单：{charge_order_id}\nuser: {user.username} {user.id}\nvolume: {charge_balance}\n钱包：{wallet_address}'
        await sender(content, self.feishu_webhook, '新的充值')
        # 3、回收钱包地址
        await self.wallet_address_sc_of_message_function(update, context)
        # 4、有充值行为的ID（int）加入白名单
        self.redis_cli.sadd(self.white_list, user.id)

    def wallet_address_source_collection(self):
        """
        钱包地址回收程序  独立线程
        异步工作：在bot启动前创建子线程，异步工作
        """
        logger.info('钱包地址回收线程开始工作')
        # 事件循环
        while True:
            # 每分钟扫一遍任务库
            time.sleep(1*60)
            needed_del_list = []
            # 迭代哈希表中的键值对
            for wallet_address, wallet_address_time in self.redis_cli.hscan_iter(self.wallets_address_sc):
                # 超过30分钟回收该地址
                if (int(time.time()) - int(wallet_address_time)) > 30*60:
                    # 不能在迭代过程中删除，可能会出问题，故待删除的field放入列表，迭代完毕后再删除
                    needed_del_list.append(wallet_address)
            # 批量删除 需要回收的钱包地址
            with self.redis_cli.pipeline(transaction=False)as pipe:
                # 遍历需要删除的 wallet_address
                for wallet_address in needed_del_list:
                    # 将任务从回收队列删除
                    pipe.hdel(self.wallets_address_sc, wallet_address)
                    logger.info(f'钱包回收，该地址已过期（超过30M：{wallet_address}')
                    # 回收：重新放回钱包库
                    pipe.sadd(self.wallets_address, wallet_address)
                # 批量提交删除指令，优化性能
                pipe.execute()

    async def wallet_address_sc_of_message_function(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        钱包地址回收程序  消息事件函数
        25分钟以内处理，超过25分钟放弃处理，交给独立回收线程处理（超过30m会自动回收）
        """
        user_data = context.user_data
        user = update.effective_user
        wallet_address = user_data['wallet_address']
        wallet_address_time = user_data['wallet_address_time']
        # 0-25分钟内，先删除独立线程X队列的任务，阻止其再次放入：再把钱包地址塞回钱包库
        if (int(time.time())-wallet_address_time) < 25*60:
            self.redis_cli.hdel(self.wallets_address_sc, wallet_address)
            self.redis_cli.sadd(self.wallets_address, wallet_address)
            logger.info(f'钱包回收，消息处理函数执行：{wallet_address} 用户：{user.username}')

    async def message_pass(self, update, samemessage_ex: int, sameuser_ex: int):
        """
        防止短时间误点击的高频发送，
        防止浑水攻击
        能放行的返回 True
        """
        query_text = ''
        query = update.callback_query
        if query:
            if query.data:
                query_text = query.data
        # 如果是内联按钮 update.message 为None
        if update.message:
            text = update.message.text
        else:
            text = ''
        user = update.effective_user
        user_id = user.id
        # 一个用户同一条消息 samemessage_ex s 内只能发送一次
        filter_content = f'{user_id}{text}{query_text}'
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

    async def charge_success(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        充值成功的交互
        回收钱包地址 + 给用户消息反馈 + 拉起键盘 + 清空用户态 user_data 缓存  + incr用户数据库余额
        """
        # incr用户数据库余额 + 告警 + 清空缓存 + 回收钱包地址
        await self.charge_balance_chage(update, context)

        # 修改完数据库后，给用户发送消息提醒
        user_data = context.user_data
        user = update.effective_user
        # 链上到账金额
        charge_balance = user_data['charge_balance']
        user_balance = await self.get_user_balance(user.id)
        content = f'已查询到您的充值金额 <b>{charge_balance}</b> U，充值成功！\n当前余额：<b>{user_balance}</b> U'
        # 如果是来自query类型的回调，那么update.message则为None
        if update.message:
            await update.message.reply_html(
                content,
                reply_markup=self.markup_cs
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=content,
                parse_mode='html',
                reply_markup=self.markup_cs
            )

        # 清空用户绑定的缓存
        user_data.clear()

        return ConversationHandler.END

    async def user_charge_status_refresh(self, update: Update, context: CallbackContext):
        """
        刷新按钮：用户充值到账状态查询：刷新按钮 事件处理
        """
        # 10s内只容许点 "刷新" 指令 1次；发送任何消息限制频率 2s 1次   (由于查询链上数据较为耗时，防止占用资源)
        pass_status = await self.message_pass(update, 10, 2)
        # 洪水攻击验证不通过
        if not pass_status:
            return
        query = update.callback_query
        # 确认按钮单击
        await query.answer()
        # 处理回调数据
        if query.data == '1':
            user_data = context.user_data
            user = update.effective_user
            # charge_order_id = user_data['charge_order_id']
            wallet_address = user_data['wallet_address']
            wallet_balance_before_charge = user_data['wallet_balance_before_charge']
            logger.info(f'开始查询用户 {user.username} wallet {wallet_address} 充值后的余额')
            # balance_now = await balance_search(wallet_address)
            # 钱包地址余额
            balance_now = await balance_search(wallet_address)
            logger.info(f'用户 {user.username} 充值后钱包 {wallet_address} 余额: {balance_now}')
            charge_balance = float(balance_now - wallet_balance_before_charge)
            # 将到账额绑定到用户态 （刷新）
            user_data['charge_balance'] = charge_balance
            # user_data['balance_now'] = balance_now
            # 充值失败，打入刷新循环
            if charge_balance == 0:
                # 刷新次数
                refresh_charge_status_num = user_data['refresh_charge_status_num']
                refresh_charge_status_num += 1
                # 创建一个具有两个按钮的内联键盘
                keyboard = [
                    [
                        InlineKeyboardButton(f"刷新{refresh_charge_status_num}", callback_data='1'),
                        InlineKeyboardButton("取消充值", callback_data='2'),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                # await update.message.reply_html('</b>尚未到账</b>，请确认链上交易已完成，并<b>刷新</b>到账状态', reply_markup=reply_markup)
                # await query.edit_message_text(text="您点击了选项 1！")
                inline_button_content = f'<b>尚未到账</b>，请确认链上交易已完成，' \
                                        f'并<b>刷新</b>到账状态（已刷新 <b>{refresh_charge_status_num-1}</b> 次）'
                await query.edit_message_text(
                    inline_button_content,
                    reply_markup=reply_markup,
                    parse_mode = 'html'
                )
                # 修改（incr）刷新次数的值
                user_data['refresh_charge_status_num'] = refresh_charge_status_num
                logger.info(f'用户 {user.username} 充值未到账，刷新：{refresh_charge_status_num-1}')
                # 这个5是表示：self.BALANCE_RE_CONFIRM
                return 5
            # 充值成功
            else:
                logger.info(f'识别到充值金额：{charge_balance}')
                result = await self.charge_success(update, context)
                return result

    async def check_tgdev_balance(self):
        """
        检查 tgdev 开发者账户余额是否紧张（阈值：10000 credits）
        如果紧张，需要发送告警给管理员
        """
        result = await self.tgdev_api.check_balance_alert()
        # 需要告警
        if result:
            if result == True:
                msg = '余额查询失败'
            else:
                msg = f'剩余：{result} credits'
            await sender(msg, self.feishu_webhook, '余额紧张')

    async def deduct(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        扣费（来源是群关系查询扣费）
        发送余额通知
        """
        user = update.effective_user
        user_data = context.user_data
        # 扣费，Deduct_fee_num会是负数  float
        Deduct_fee_num = user_data.get('Deduct_fee_num',0)
        # 可能存在这种情况，但是不确定哪里会出现
        if Deduct_fee_num == 0:
            logger.error(f'异常扣费调用：{user.username}')
            return
        # 执行扣费
        self.redis_cli.hincrbyfloat(self.users_balance_key, user.id, Deduct_fee_num)
        # 发送扣费后余额通知
        user_balance = await self.get_user_balance(user.id)
        if user_balance < 0.2:
            content = f'当前余额：<b>{user_balance}</b> U \n<b>余额不足，请👉🏻充值</b>'
        else:
            content = f'当前余额：<b>{user_balance}</b> U'
        # 清空缓存
        user_data.clear()
        # 校验tgdev 余额是否紧张，紧张则告警
        await self.check_tgdev_balance()
        # 邀请奖励按钮
        referral_button = await self.referral_program.gen_invite_button(update, context)
        await update.message.reply_html(
            content,
            reply_markup=referral_button
        )