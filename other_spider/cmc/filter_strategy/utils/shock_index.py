
def shock_index_computing(ma_index, shock_amp):
    """
    计算震荡指数
    """
    # 对横盘的ma指数校正，使其偏离极小值
    if ma_index >= 0:
        # 往上拉
        # ma_index = ma_index + 2
        # ma_index_amp_farawaytoomini = round((ma_index + pow(10 / ma_index, 1.3)), 4)
        ma_index = ma_index + 25
        ma_index_amp_farawaytoomini = round((ma_index + pow(50 / ma_index, 1.8)), 4)
    else:
        # 往上拉
        ma_index = -ma_index
        ma_index = ma_index + 25
        res = round((ma_index + pow(50 / ma_index, 1.8)), 4)
        ma_index_amp_farawaytoomini = -res
    # 对ma指数进行校正(基于上一个校正结果)，使其偏离极大值
    if ma_index_amp_farawaytoomini > 0:
        # 往下拉
        # 当斜率400时被拉的过大了，不合适
        # shock_amp_farawaytoomax = round(ma_index_amp_farawaytoomini - pow((ma_index_amp_farawaytoomini / 20), 2), 4)
        shock_amp_farawaytoomax = round(ma_index_amp_farawaytoomini - pow((ma_index_amp_farawaytoomini / 400), 10), 4)
    else:
        # 往下拉
        shock_amp_farawaytoomax = round(ma_index_amp_farawaytoomini + pow((ma_index_amp_farawaytoomini / 400), 10), 4)
    shock_index = round((shock_amp / shock_amp_farawaytoomax), 3)
    return shock_index