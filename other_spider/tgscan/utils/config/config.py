import os
#推荐用户的奖励
referral_bonus = 0.1
# Telegram 用户 ID 白名单，逗号分隔
white_list = [int(x) for x in os.getenv('TGSCAN_WHITE_LIST', '').split(',') if x.strip()]
white_list_rediskey = 'tgscan:whitelist'
# 新用户（含有用户名的，赠送额度）
new_real_user_bonus = 0.1
new_fake_user_bonus = 0
# 单次查询的扣费金额
Deduct_fee_num = -0.2
# 收款钱包地址，逗号分隔
addresses = [x for x in os.getenv('TGSCAN_WALLET_ADDRESSES', '').split(',') if x.strip()]