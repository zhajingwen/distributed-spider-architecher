import logging
from numpy import *
import pandas as pd
from utils.redisdb import redis_cli
# 5m 动量计算
from other_spider.cmc.filter_strategy.utils.big_decreased_candle import K_strong_status

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CCXT 1M')


class Ma1M:

    def __init__(self, ohlcv, name, id, market, normal_5mk_length_cmc):
        # 剔除统计区间后的最后一个价格
        # self.old_num = old_num
        # 100根K线的list
        self.candle_list = ohlcv
        self.name = name
        self.redis_cli = redis_cli()
        # self.price_diff = price_diff
        # self.diff_time = diff_time
        self.black_key_base = f'cmc:black:{market}:'
        self.key = self.black_key_base + str(id)
        self.normal_5mk_length_cmc = normal_5mk_length_cmc
        self.market = market

    def no_on_highpirce(self, price_increased_num):
        """
        price_increased_num: 价格起涨的index
        计算统计区间外，最近5分钟内最高价高于99单位均线的幅度
        如果是高于均线的，算最高价，如果是低于均线的算最低价
        最近1m 5根
        """
        num = 0
        prices = []
        start_increase_price = list(reversed(self.candle_list))[price_increased_num][4]
        for p in list(reversed(self.candle_list)):
            num += 1
            if num > price_increased_num:
                prices.append(p[4])
            if num > 98:
                break
        # 99单位均线，当前时间点的（统计区间外）的价格点（均价）
        average_price = mean(prices)
        # 偏离幅度计算
        diff_amputide = ((start_increase_price - average_price)/average_price)*100
        return diff_amputide

    def shock_amplitude(self, window_lenght, price_increased_num, average_k_length):
        """
        振幅:
        最近 window_lenght 根k线最高价到最低价的振幅
        """
        num = 0
        lowest_price = []
        highest_price = []
        new_price_list = []
        for p in list(reversed(self.candle_list)):
            num += 1
            if num - price_increased_num > window_lenght:
                break
            if num > price_increased_num:
                lowest_price.append(p[3])
                highest_price.append(p[2])
                new_price_list.append(p[4])
        price_shock_amp = ((max(highest_price)-min(lowest_price))/min(lowest_price))*100
        # 区间涨幅
        unilateral_market_priceshock_amp = ((new_price_list[0] - new_price_list[-1]) / new_price_list[-1]) * 100

        # 判断是否是单边行情的指数
        increased_abs_to_amp_ratio = abs(unilateral_market_priceshock_amp) / price_shock_amp
        # 单边下跌的行情，振幅乘以系数2/3
        if unilateral_market_priceshock_amp < 0:
            # 单边下跌的幅度大于振幅的0.3倍，且单边幅度大于3倍的k线长度   认为是单边下跌趋势
            if increased_abs_to_amp_ratio > 0.3 and (abs(unilateral_market_priceshock_amp)/3 > average_k_length):
                # 单边下跌，振幅豁免系数2/3
                price_shock_amp_excellent = abs(price_shock_amp)*(2/3)
            else:
                price_shock_amp_excellent = price_shock_amp
        # 单边上涨
        else:
            # 20分钟满足1.5倍平均涨幅（5m）就认为是单边，50分钟，大于2.5倍就认为是单边
            # 20
            if window_lenght <= 25:
                threshold = 1
            # 50
            else:
                threshold = 2
            # 单边行情的涨幅 大于振幅的0.3倍，且单边幅度大于 threshold 倍的k线长度  认为是单边上涨趋势
            if increased_abs_to_amp_ratio > 0.3 and (abs(unilateral_market_priceshock_amp)/threshold > average_k_length):
                price_shock_amp_excellent = price_shock_amp*1.7
            else:
                price_shock_amp_excellent = price_shock_amp

        # logger.info(f'debug {price_shock_amp_excellent}  {average_k_length}')
        # if average_k_length == 0:
        #     logger.info(f'average_k_length为0{self.name} {self.candle_list}')
        logger.info(
            f'{self.name} 单边行情；涨幅：{unilateral_market_priceshock_amp};'
            f'振幅：{price_shock_amp};klen: {average_k_length}'
        )

        # 加权振幅
        w_price_shock_amp = round((price_shock_amp_excellent/average_k_length),3)
        return w_price_shock_amp

    def pass_verify(self):
        """
        所有对于交易所返回的1分钟单位的K线数据的策略都在这里汇总
        """
        # 1m k线的平均长度
        average_k_length = self.candle_average_length()
        if not average_k_length:
            return
        # optimizaton the computation of price increased
        # compute the average price increased amplitude
        price_incresed_dataaggregation = self.price_increased_amp(average_k_length)
        if not price_incresed_dataaggregation:
            return
        else:
            price_diff,diff_time_window,price_increased_num,now_price = price_incresed_dataaggregation
            price_incresed_average = round(price_diff/diff_time_window,3)
        # price far to 99ma amplitude
        on_high_amp = self.no_on_highpirce(price_increased_num)
        # 如果价格在均线99ma下方太多，过滤
        # 均线99ma下方的跌幅大于上涨的幅度，过滤
        if on_high_amp < 0:
            if abs(on_high_amp) > price_diff:
                logger.info(f'{self.name} 1m 99ma 价格算上涨幅仍然在均线下方 {on_high_amp}%')
                return
        if not self.no_exsit_negative_candle(average_k_length, price_increased_num, price_diff):
            return
        # # 均线99ma上方偏离的幅度 大于价格涨幅（1分钟）的1.7倍
        # if (self.price_diff/self.diff_time) * 1.7 < on_high_amp:
        #     logger.info(f'{self.name} 1m 99ma 价格距离均线落差大于1.7倍的当前价格涨幅 {on_high_amp}%')
        #     return False
        #
        # # 这个条件的愿景是其实价格波动幅度本来就很小，但是历史价格却在均线上方太多，就不合理
        # if (on_high_amp > 1) and (self.price_diff * 1.5 < on_high_amp):
        #     logger.info(f'{self.name} 1m 99ma 价格距离均线落差大于价格涨幅的1.5倍 {on_high_amp}%')
        #     return False
        # amplitude_10m = self.lowest_to_highest(10)
        # # 该策略有疏忽 没有考虑不同币的脾性
        # # if amplitude_10m > 2:
        # #     logger.info(f'{self.name} 最近10根1m K线振幅大于2% {amplitude_10m}%')
        # #     return False
        # if self.price_diff * 1.5 < amplitude_10m:
        #     logger.info(f'{self.name} 最近10根1m K线振幅大于涨幅的1.5倍 {amplitude_10m}%')
        #     return False

        # there is not big decreased candle in near 50 minute
        kstrong_50m = self.no_big_decrease()
        if not kstrong_50m:
            return
        # 5m 10单位的振幅指数（没有复合均线）
        prices_5m = self.price_transform_to_5m()
        candle_ave_len_5m = self.candle_average_length_5m(prices_5m)
        if not candle_ave_len_5m:
            logger.error('5分钟平均长度为0')
            return
        amplitude_50m = self.shock_amplitude(50, price_increased_num, candle_ave_len_5m)
        # 振幅大于4 or 6过滤       如果当前涨幅很大，可以忽略前面的震荡
        if amplitude_50m > 4 and (price_incresed_average/candle_ave_len_5m < 4):
            # 防止旗形走势被误杀
            amplitude_20m = self.shock_amplitude(20, price_increased_num, candle_ave_len_5m)
            # 考虑快速拉升的情况，可以对前面的震荡做宽松处理
            if (amplitude_20m > 2 and price_incresed_average/candle_ave_len_5m < 2) or (amplitude_50m > 6 and price_incresed_average/candle_ave_len_5m < 7):
                value = f'{self.name} 1m 50单位振幅过大 {amplitude_50m} ' \
                        f'20单位：{amplitude_20m} 涨幅：{price_incresed_average} K线平均长度：{candle_ave_len_5m}'
                logger.info(value)
                # self.redis_cli.set(self.key, value, ex=5 * 60)
                return
        # 价格偏离5m 10ma 的距离
        price_to_5m_amp = self.price_to_5m_shockamp()
        if not price_to_5m_amp:
            return
        # 1m 价格列表
        prices = []
        for p in self.candle_list:
            # 收盘价
            prices.append(p[4])
        # 价格偏离10ma
        slop_10ma, price_to_1m_10ma = self.ma_trend_and_price(prices[:-1],average_k_length,10)
        # 价格偏离25ma
        slop_25ma, price_to_1m_25ma = self.ma_trend_and_price(prices[:-1],average_k_length,25)
        value = f'{self.name} 1m 偏离10ma: {price_to_1m_10ma} 偏离25ma: {price_to_1m_25ma}'
        logger.info(value)
        if price_to_1m_10ma > 2.5 and price_to_1m_25ma > 3.5:
            self.redis_cli.set(self.key, value, ex=2 * 60)
            return
        # 100分钟无大阴线
        k_strong_sta_100m = K_strong_status(prices_5m, 20, candle_ave_len_5m, self.name, 'ccxt', '5m')
        if not k_strong_sta_100m:
            return
        else:
            logger.info(f'{self.name} ccxt  k_strong_sta_100m: {k_strong_sta_100m}')
        # 12m 无大阴线
        k_strong_sta_12m = K_strong_status(prices, 12, average_k_length, self.name, 'ccxt', '1m')
        if not k_strong_sta_12m:
            return
        else:
            logger.info(f'{self.name} ccxt  k_strong_sta_12m: {k_strong_sta_12m}')
        # 12*5分钟无大阴线
        k_strong_sta = K_strong_status(prices_5m, 12, candle_ave_len_5m, self.name, 'ccxt', '5m')
        if not k_strong_sta:
            return
        volume = self.volume()
        # 成交额不满足条件过滤
        if not volume:
            return
        # 1m级别不是放量上涨过滤
        volume_1m_rank = self.volume_increased(price_increased_num)
        if not volume_1m_rank:
            return
        # 6小时内 非量价齐升过滤
        priceup_volumeup = self.price_and_volume_relationship()
        if not priceup_volumeup:
            return
        # 最近50根K线加权振幅，价格平均没分钟的涨幅，价格2分钟内的累计涨幅，价格上涨的时间, 当前价
        return amplitude_50m,price_incresed_average,price_diff,diff_time_window,now_price,volume
        # if self.K_strong_recent30m(ohlcv, num, name) and \
        #         self.no_big_decrease(ohlcv,name) and \
        #         (on_high_amp < 2):

    def candle_average_length(self):
        """
        计算最近30根K线的平均长度
        """
        num = 0
        leng_list_origin = []
        for p in list(reversed(self.candle_list)):
            num += 1
            if num > 30:
                break
            price_increase_amplitude = ((p[4] - p[1])/p[1])*100
            candle_length = round(abs(price_increase_amplitude),3)
            leng_list_origin.append(candle_length)
        # 剔除极值，防止对于平均的计算造成干扰 包含极端大和极端小的比如横盘
        kill_extremely_after = list(reversed(sorted(leng_list_origin)))[2:7]
        # 平均长度
        average_length = float(mean(kill_extremely_after))
        average_length = round(average_length,3)
        # 存在极其不活跃的币，导致1mK线平均长度为0
        if not average_length:
            logger.info(f'{self.name} 平均K线长度为0')
            return
        return average_length

    def no_exsit_negative_candle(self, average_k_length, price_increased_num, price_diff):
        """
        最近30个1分钟K线无大阴线
        """
        num = 0
        # 阴线列表
        negative_numbers = []
        # 阳线列表
        positive_numbers = []
        # 涨速统计区间的K线阳线长度列表
        compute_interval_numbers = []
        for p in list(reversed(self.candle_list)):
            num += 1
            price_increase_amplitude = ((p[4] - p[1])/p[1])*100
            if price_increase_amplitude < 0:
                # 把下跌的上影线也算上
                price_increase_amplitude = ((p[4] - p[2]) / p[2]) * 100
                candle_length = round(abs(price_increase_amplitude), 3)
                negative_numbers.append(abs(candle_length))
            else:
                candle_length = round(abs(price_increase_amplitude), 3)
                positive_numbers.append(candle_length)
            if num <= price_increased_num:
                if candle_length > 0:
                    compute_interval_numbers.append(candle_length)
        # 统计区间之前的最长k线如果是阴线，过滤
        if max(negative_numbers) > max(positive_numbers):
            # 如果出现大阴线，并且大阴线的长度是最近30根k线平均长度的4倍以上，过滤
            if max(negative_numbers) > (4*average_k_length):
                if max(negative_numbers) > (4*price_diff):
                    logger.info(f'{self.name} 最近30分钟有大阴线且是平均k线长度的4倍以上{max(negative_numbers)} - {price_diff}')
                    return
        return True
        # # 统计区间内的最长的阳线长度是最近30最长的K线才能通过
        # else:
        #     if max(compute_interval_numbers) > max(negative_numbers):
        #         return True
        #     else:
        #         logger.info(f'{self.name} 最近30分钟有大阴线')
        #         return False
    def price_increased_amp(self, average_k_length):
        """
        compute the price incresed amplitude and time consuming
        """
        # now_price = ohlcv[-1][4]
        # 可能是空列表的情况
        if not self.candle_list:
            return
        try:
            now_price = self.candle_list[-1][4]
        except:
            logger.error(f'{self.name} ccxt越界')
            return
        now_time = int(self.candle_list[-1][0] / 1000)
        # 当前价往前推算，看看第几分钟满足大于3%的涨幅
        num = 0
        alert = False
        # ohlcv 中包含了当前价，计算涨幅应该拿当前价-开盘价往前递推
        for p in list(reversed(self.candle_list)):
            num += 1
            # 计算涨幅 当前价-开盘价/开盘价
            price_diff = ((now_price - p[1]) / p[1]) * 100
            # 如果 2分钟之内涨幅超过百分之0.3的报警
            if (num >= 1 and num < 3):
                if price_diff > 0.3:
                    alert = True
                else:
                    # 部分币1m波动极小，可能是0.05%/m  这个时候如果涨幅能够超过其平均k线长度的2倍，那么也是符合要求的
                    if price_diff/average_k_length > 2:
                        alert = True
                    else:
                        # 一根K线的涨幅能大于平均K线程度也通过
                        if num == 1 and price_diff > average_k_length:
                            alert = True
            # 优化计算，不做无谓的循环
            else:
                break
            if alert:
                # 耗时 分钟为单位
                diff_time = (now_time - int(p[0] / 1000)) / 60
                # 由于k线数据对包含了当前时间，故得+1
                diff_time += 1
                # 返回涨幅，耗时（/m）
                return price_diff,diff_time,num,now_price
        logger.info(f'{self.name} 1分钟之内涨幅不满0.3%')
        return alert
        #         # 交易所k线数据规则汇总过滤
        #         pass_status_1m = Ma1M(num, ohlcv, name, price_diff, diff_time).pass_verify()
        #         if pass_status_1m == False:
        #             return
        #         if self.no_big_decrease(ohlcv,name):
        #             logger.info(f'{name} {diff_time}分钟涨幅 {price_diff}')
        #             data = {
        #                 # 'ohlcv': ohlcv,
        #                 'price_diff': price_diff,
        #                 'diff_time': int(diff_time),
        #                 'price_usd':now_price,
        #                 'marketPair': marketPair.replace('/','_'),
        #                 'shock_amp_50m':pass_status_1m
        #                 # 'on_high_amp':on_high_amp,
        #                 # 'amplitude_10m':amplitude_10m
        #             }
        #             return data
        #         else:
        #             return False
        # logger.info(f'{name} 1分钟之内涨幅不满0.3%')
        # return False

    def no_big_decrease(self):
        """
        最近的50个单位的1分钟K线没有出现跌幅超过1.5%的
        跌幅不超过1.5%的返回True
        """
        num = 0
        status = True
        for p in list(reversed(self.candle_list)):
            num += 1
            if num < 51:
                # 价差
                diff_price = p[4] - p[1]
                # 涨幅
                amplitude = (diff_price / p[1]) * 100
                # 涨幅如果是跌的，并且小于 -1.5%，那么
                if amplitude < -1.5:
                    logger.info(f'{self.name} 前50根K线存在跌幅大于1.5%的情况{amplitude} {p[0]}')
                    status = False
                    break
            else:
                break
        return status

    def before_have_increase(self, old_num, name):
        """
        确保前20分钟内没怎么涨，此策略为了规避买在顶点，买在行情末端
        """
        num = 0
        # 是否已经涨过了
        have_increased = False
        # 拿涨速报警统计区间之前的最近一个收盘价为价格基准；
        the_end_price = list(reversed(self.candle_list))[old_num + 1][4]
        for p in list(reversed(self.candle_list)):
            num += 1
            if num > old_num:
                num_diff = num - old_num
                # 计算涨幅 当前价-开盘价/开盘价
                price_diff = ((the_end_price - p[1]) / p[1]) * 100
                # 涨速测试区间前的1-2分钟内如果涨幅超过了1那么就过滤掉
                if (num_diff >= 1 and num_diff < 3):
                    if price_diff > 1:
                        have_increased = True
                # 涨速测试区间前的3-5分钟内如果涨幅超过了1.5那么就过滤掉
                elif (num_diff < 6 and num_diff >= 3):
                    if price_diff > 1.5:
                        have_increased = True
                # 涨速测试区间前的6-10分钟内如果涨幅超过了3那么就过滤掉
                elif num_diff < 11:
                    if price_diff > 2:
                        have_increased = True
                # 涨速测试区间前的10-25分钟内如果涨幅超过了5那么就过滤掉
                elif (num_diff >= 11 and num_diff < 25):
                    if price_diff > 2.5:
                        have_increased = True
                else:
                    if price_diff > 3:
                        have_increased = True
                if have_increased:
                    logger.info(f'{name} 已经涨过了{num_diff}分钟涨幅 {price_diff}')
                    break
        return have_increased

    def price_transform_to_5m(self):
        """
        剔除当前价的5m价格点列表
        """
        prices = []
        num = 0
        for p in self.candle_list:
            num += 1
            if (num == 1) or (num%5==0):
                prices.append(p[4])
        return prices


    def candle_average_length_proofreading(self, prices, window):
        """
        为了避免最近的横盘震荡对K线价格反馈失真的情况出现，99单位和288单位均价择大录用
        """
        if window == 96:
            # 截取最近96*5m单位的K线价格 约占34%
            new_prices = list(reversed(prices[-96:]))
        elif window <= 20:
            if len(prices) > 20:
                # 截取最近20*5m单位的K线价格
                new_prices = list(reversed(prices[-20:]))
            # 兼容mainex数据
            else:
                new_prices = list(reversed(prices))
        elif window == 40:
            # 40单位
            new_prices = list(reversed(prices[-40:]))
        else:
            new_prices = list(reversed(prices))
        num = 0
        leng_list_origin = []
        for r_price in new_prices:
            num += 1
            # 防止越界
            if num > (len(new_prices) -1):
                break
            price_increase_amplitude = ((r_price - new_prices[num])/new_prices[num])*100
            # 绝对值精确到3位小数
            price_increase_amplitude = round(abs(price_increase_amplitude),3)
            leng_list_origin.append(price_increase_amplitude)
        # 剔除极值，防止对于平均的计算造成干扰 包含极端大和极端小的比如横盘
        if  window == 96:
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[3:23]
        elif window <= 20:
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[1:5]
        elif window == 40:
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[2:12]
        else:
            # 200单位
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[6:46]
        # 平均长度
        average_length = float(mean(kill_extremely_after))
        average_length = round(average_length,3)
        return average_length

    def candle_average_length_5m(self, prices):
        """
        5m平均k线长度
        1000单位的Limi 是200个价格点(处理过的5m的价格点)
        """
        # average_length = self.candle_average_length_proofreading_5m(prices)
        # new_prices = list(reversed(prices))
        # num = 0
        # leng_list_origin = []
        # for r_price in new_prices:
        #     num += 1
        #     # 防止越界
        #     if num > (len(new_prices) -1):
        #         break
        #     price_increase_amplitude = ((r_price - new_prices[num])/new_prices[num])*100
        #     # 绝对值精确到3位小数
        #     price_increase_amplitude = round(abs(price_increase_amplitude),3)
        #     leng_list_origin.append(price_increase_amplitude)
        # 剔除极值，防止对于平均的计算造成干扰 包含极端大和极端小的比如横盘
        # kill_extremely_after = list(reversed(sorted(leng_list_origin)))[2:-5]
        # 平均长度
        # average_length = float(mean(kill_extremely_after))
        # average_length = round(average_length,3)
        # 只有binace是1000单位的olhcv
        if self.market == 'binance':
            # 取最大的平均数最为整体的K线平均长度，为了规避对于某些不活跃的币种突然变得活跃了的计算偏差
            average_length_20 = self.candle_average_length_proofreading(prices,20)
            average_length_40 = self.candle_average_length_proofreading(prices,40)
            average_length_99 = self.candle_average_length_proofreading(prices,99)
            average_length_199 = self.candle_average_length_proofreading(prices,199)
            average_length = max(average_length_20,average_length_40,average_length_99,average_length_199)
        else:
            average_length = self.candle_average_length_proofreading(prices,19)
        return max(average_length,self.normal_5mk_length_cmc)

    def ma_trend_and_price(self, prices, normal_k_length, window_size):
        """
        计算均线加权斜率 和 加权价格偏离均线的指数(绝对值)
        如果是10ma，均线用2个单位的长度计算
        如果是25ma，均线用5个单位的长度计算
        价格列表最后一个元素计算
        """
        numbers_series = pd.Series(prices)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))

        compute_interval = 10
        if window_size == 10:
            compute_interval = 2
        if window_size == 25:
            compute_interval = 5
        if window_size == 99:
            compute_interval = 10
        if window_size == 150:
            compute_interval = 15
        # 计算斜率
        increase_amplitude = ((new_ma_list[0] - new_ma_list[compute_interval]) / new_ma_list[compute_interval]) * 100
        increase_amplitude = round(increase_amplitude, 3)
        # 加权斜率
        slop = round((increase_amplitude / normal_k_length) * 100, 2)

        price_to_ma_shock_amplitude = ((prices[-1]-moving_averages_list[-1])/moving_averages_list[-1])*100
        price_to_ma_shock_amplitude = round(price_to_ma_shock_amplitude/normal_k_length,3)

        # 加权趋势和价格偏离均线的加权幅度
        return slop,price_to_ma_shock_amplitude

    def price_to_5m_shockamp(self):
        """
        价格到 10单位的距离指数
        """
        prices = self.price_transform_to_5m()
        normal_k_length = self.candle_average_length_5m(prices)
        if not normal_k_length:
            logger.error('5分钟平均长度为0')
            return
        increase_amplitude_weighted,price_to_ma_shock_amplitude = self.ma_trend_and_price(prices,normal_k_length,10)
        if abs(price_to_ma_shock_amplitude) > 0.9:
            # 为了避免 normal_k_length 过小导致对于实际的波动情况反馈失真
            if abs(price_to_ma_shock_amplitude)*normal_k_length > 0.9:
                value = f'{self.name}5m(1m) 加权价格偏离10ma指数过大{price_to_ma_shock_amplitude}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=1 * 5 * 60)
                return
        return price_to_ma_shock_amplitude

    def volume_(self, window):
        """
        window: 30 or 60
        30分钟级别和60分钟级别
        """
        all_hours_data = []
        hour_volume_decreased = 0
        hour_volume_increased = 0
        for index, p in enumerate(list(reversed(self.candle_list))):
            # 每小时初始化一次
            if index % window == 0:
                hour_volume_decreased = 0
                hour_volume_increased = 0

            # 判断涨跌
            price_increase_amplitude = ((p[4] - p[1]) / p[1]) * 100
            if price_increase_amplitude < 0:
                # 累计成交量
                hour_volume_decreased += p[5]
            else:
                hour_volume_increased += p[5]
            # 将当前 window 分钟的数据汇入统计列表
            if index % window == (window-1):
                hour_volume_decreased = int(hour_volume_decreased) * -1
                hour_data = [hour_volume_decreased, int(hour_volume_increased)]
                all_hours_data.append(hour_data)
        # 成交额 价格乘以成交量
        volume_usdt = self.candle_list[-1][4] * (all_hours_data[0][1] - all_hours_data[0][0])
        # 过滤最近1小时成交额小于 3w U
        if volume_usdt < (30000/60)*window:
            value = f'{self.name} 1m 成交额太小 {window} {volume_usdt}'
            logger.info(value)
            return
        # binance
        if len(all_hours_data) > 1:
            # 当前区间的交易量
            volume_now_total = all_hours_data[0][1] + abs(all_hours_data[0][0])
            # 上一个区间的交易量
            volume_last_total = all_hours_data[1][1] + abs(all_hours_data[1][0])
            # 成交量剧烈下滑过滤
            if volume_last_total > volume_now_total * 1.5:
                logger.info(f'{self.name} {window} 成交总量剧烈下滑')
                return
                # 买入量递增                                           买入量大于卖出量
            if (all_hours_data[0][1] > all_hours_data[1][1]) and (all_hours_data[0][1] > abs(all_hours_data[0][0])):
                # 每小时内下跌的成交量和上涨成交量的列表
                return all_hours_data
            else:
                value = f'{self.name} 1m {window}m成交量不符合递增条件  {all_hours_data}'
                logger.info(value)
                return '复合'
        # mainex
        else:
            return all_hours_data

    def volume(self):
        """
        成交量统计 30分钟 or 60分钟
        30分钟成交量递增作为必要条件
        """
        volume_60 = self.volume_(60)
        volume_30 = self.volume_(30)
        if volume_60:
            if volume_60 == '复合':
                # 30分钟满足递增
                if volume_30 and volume_30 != '复合':
                    logger.info(f'{self.name} 1m 成交量30m 满足')
                    return volume_30
            # 60分钟满足递增
            else:
                logger.info(f'{self.name} 1m 成交量60m 满足')
                # 30分钟满足递增
                if volume_30 and volume_30 != '复合':
                    logger.info(f'{self.name} 1m 成交量30m 满足')
                    return volume_30
        return

    def volume_increased(self, price_increased_num):
        """
        上涨的成交量是否满足条件
        """
        # 最近30分钟成交量的列表
        volumes_30 = []
        for index, p in enumerate(list(reversed(self.candle_list))):
            # 拿最近30分钟的成交量
            if index > 29:
                break
            volume = p[5]
            volumes_30.append(volume)
        rank = 30
        # 上涨时的成交量
        increased_volume = sum(volumes_30[:price_increased_num])/price_increased_num
        rank_list = list(reversed(sorted(volumes_30)))
        for index,p in enumerate(rank_list):
            # 得是>=因为列表中包含了increased_volume自己
            if increased_volume >= p:
                rank = index
                break
        # 如果上涨的成交量第二名都排不上就过滤
        if rank > 1:
            value = f'{self.name} 1m上涨无量最近30分钟排不上第二名 {increased_volume} {rank_list}'
            logger.info(value)
            return
        return True

    def price_and_volume_relationship(self):
        """
        价涨量缩过滤
        半个小时为单位
        如果过关 返回True
        """
        status = True
        # 30分钟成交量
        volume_30m = 0
        # 30分钟内的价格列表
        prices_30m = []
        olhcv = list(reversed(self.candle_list))
        price_volume = []
        for index, p in enumerate(olhcv):
            # 只比较最近6小时数据
            if index > 6*60:
                break
            # 每30m初始化一次
            if index % 30 == 0:
                volume_30m = 0
                prices_30m = []
            volume_30m += p[5]
            prices_30m.append(p[2])
            # 统计数据
            if index % 30 == 29:
                highest_price = max(prices_30m)
                price_volume.append([highest_price,volume_30m])
        now_price_highest = price_volume[0][0]
        now_volume = price_volume[0][1]
        for item in price_volume[1:]:
            price,volume = item
            # 一旦出现了价格比当前价要低，但是成交量比当前成交量高
            if price < now_price_highest:
                if volume > now_volume:
                    logger.info(f'{self.name}  30m价涨量缩')
                    status = False
        return status