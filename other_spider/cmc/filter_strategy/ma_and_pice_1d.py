import logging
import time
import heapq
import numpy
import requests
from functools import wraps
from traceback import format_exc
import pandas as pd
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from .increase_candle_more import PirceCheck
from other_spider.cmc.filter_strategy.utils.shock_index import shock_index_computing
from other_spider.cmc.filter_strategy.utils.big_decreased_candle import K_strong_status

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC MA 1D')



class Ma:
    def __init__(self, id, name, market):
        self.url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart?id={id}&range=1D'
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7",
            "cache-control": "no-cache",
            "dnt": "1",
            "origin": "https://coinmarketcap.com",
            "platform": "web",
            "referer": "https://coinmarketcap.com/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            # "x-request-id": "49fe75f8289d4bffa86643a8f0e08f50"
        }
        self.name = name
        self.redis_cli = redis_cli()
        self.id = id
        self.black_key_base = f'cmc:black:{market}:'
        self.key = self.black_key_base + str(self.id)


    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10

        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'ConnectionRefusedError' in error:
                            logger.warning(f'{func.__name__} ConnectionRefusedErr')
                        elif 'json.decoder.JSONDecodeError' in error:
                            logger.warning(f'{func.__name__} JSONDecodeErr')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning('重试超过次数')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry()
    def req1d_pirces(self):
        """
        请求一天的价格数据
        """
        # price_usd = float(price_usd)
        res = requests.get(self.url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'1D状态码错误：{self.name} {res.status_code}')
        logger.info(f'{self.name} {res.status_code}: {self.url}')
        try:
            res.json()
        except:
            logger.warning(f'{self.name}日线数据json()失败：{self.url}')
            raise Exception('res json 错误')
        try:
            res.json()['data']['points']
        except:
            logger.warning(f'{self.name}数据体异常 {self.url}')
            raise Exception('res points 错误')
        return res

    def ma_strategy_25(self, res, normal_k_length):
        """
        通过均线的走势
        均线与价格的关系
        产生三个条件，三个条件都满足的时候，那么就买入
        """
        points = res.json()['data']['points']
        window_size = 25
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        # 剔除当前价的干扰,剔除1个单位
        prices.pop()
        # prices.pop()
        numbers_series = pd.Series(prices)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 存放历史价格与均线的价差比例 单位%
        diffs = []
        num = 0
        for i in prices:
            num += 1
            index = num - 1
            # 防止溢出
            if index > len(moving_averages_list)-1:
                break
            if moving_averages_list[index]:
                diff = ((i-moving_averages_list[index])/i)*100
                diff = round(diff,3)
                diffs.append(diff)
            else:
                diffs.append(0)
        # 条件1
        # 过去100个单位diff(均线与价差) 绝对值在5% 以内震荡
        # 如果diff_100unit_status为 True那么就没有问题，否则过滤
        diff_100unit_status = True
        # d_num = 0
        # for d in reversed(diffs):
        #     d_num += 1
        #     if d_num < 101:
        #         if abs(d) > 5:
        #             diff_100unit_status = False
        #             value = f'{int(time.time())}{self.name}5分钟粒度，过去100个单位价格与均线的差值存在大于5%的情况{d}'
        #             logger.info(value)
        #             self.redis_cli.set(self.key, value, ex=10 * 60)
        #             break
        #     else:
        #         break
        # 条件2
        # 过去9个单位，diff可能出现负值的情况，负值不小于 1%；正值不大于5%
        # d_num = 0
        diff_9unit_status = True
        # for d_9 in reversed(diffs):
        #     d_num += 1
        #     if d_num < 10:
        #         if d_9 < 0:
        #             # 均线下方的价格，和均线的差值不能大于1%
        #             if abs(d_9) > 1:
        #                 diff_9unit_status = False
        #                 value = f'{int(time.time())}{self.name}5分钟粒度，过去9个单位价格与25ma均线的差值小于1%的情况{d_9}'
        #                 logger.info(value)
        #                 self.redis_cli.set(self.key, value, ex=10 * 60)
        #                 break
        #         else:
        #             # 均线上方的价格，和均线的差值不能大于5%
        #             if d_9 > 5:
        #                 diff_9unit_status = False
        #                 logger.info(f'{self.name} 5分钟粒度，过去9个单位价格与均线的差值大于5%的情况{d_9}')
        #                 value = f'{int(time.time())}{self.name}5分钟粒度，过去9个单位价格与均线的差值大于5%的情况{d_9}'
        #                 self.redis_cli.set(self.key, value, ex=10 * 60)
        #                 break
        #     else:
        #         break
        # 条件3
        # 均线可能下行，跌速，每单位小于0.05%
        new_ma_list = list(reversed(moving_averages_list))
        # a_p_num = 0
        # ma_increase_status = True
        # increase_amplitude_list = []
        # for average_price_25 in new_ma_list:
        #     a_p_num += 1
        #     if a_p_num < 10:
                # 3个单位的间距比较适合25ma
            #     increase_amplitude = ((average_price_25 - new_ma_list[a_p_num+2])/new_ma_list[a_p_num+2])*100
            #     increase_amplitude_list.append(increase_amplitude)
            # else:
            #     break
        # minex_increase_amp = min(increase_amplitude_list)
        # 因为25单位的均线极其的平滑，相邻的两个单位之间几乎看不出价差，需要5单位间距进行计算
        trend_25ma_amp = ((new_ma_list[0] - new_ma_list[5]) / new_ma_list[5]) * 100
        # 加权斜率
        trend_25ma_amp = round((trend_25ma_amp/normal_k_length)*100, 3)
        logger.info(f'{self.name} 5分钟粒度，加权25ma {trend_25ma_amp}%')
        if trend_25ma_amp < -70:
        # if trend_25ma_amp < 0:
            # ma_increase_status = False
            value = f'{int(time.time())}{self.name} 5M 25个单位均线下行并且速度快于 {trend_25ma_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=2*5 * 60)
        # 条件4
        # 如果25ma 99ma 都是下跌趋势，那么剔除
        trend_99_amp = self.ma_99_trend_and_price(res,normal_k_length)
        if not trend_99_amp:
            return
        # 99ma amp
        trend_99_amp_slop = trend_99_amp[0]
        # 理论上的阈值应该都是0，由于cmc数据经常存在失真，为了不误杀，这里设置为-10
        if (trend_99_amp_slop < -10) and (trend_25ma_amp < -10):
            value = f'{self.name}5M 25ma和99ma同时下跌趋势 99ma{trend_99_amp_slop},25ma{trend_25ma_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=5 * 5 * 60)
            return
        # 条件5
        # 起涨时的价格距离25单位均线的幅度
        now_price_to_25ma_distance = abs(list(reversed(diffs))[0])
        # 加权偏离25ma 的幅度
        now_price_to_25ma_distance = round((now_price_to_25ma_distance/normal_k_length)*100,3)
        # 前面三个条件
        if diff_100unit_status and diff_9unit_status:
            return now_price_to_25ma_distance,trend_25ma_amp
        else:
            return

    def price_increased(self, res):
        """
        价格涨幅在两个单元内（时间间隔5-10分钟）得大于1.5%
        这是第一次价格过滤，通过后会传递给交易所获取数据进行第二次价格过滤
        如果通过，那么返回涨幅，否则返回False
        """
        points = res.json()['data']['points']
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        # 当前价
        the_last_pirce = prices[-1]
        prices.pop()
        num = 0
        increase_status = False
        # 初始化
        price_increase_amplitude = 0
        for r_price in reversed(prices):
            num += 1
            # 最多计算两个单元
            if num <= 2:
                price_increase_amplitude = ((the_last_pirce - r_price)/r_price)*100
                # 理想情况应该设置成1.5，考虑到cmc的行情又滞后，并且可能存在价差，所以就增加了弹性空，阈值设置成0.2
                # 由于延迟实在太大，这里改成-0.5
                if price_increase_amplitude > -0.5:
                    # 将涨幅返回
                    increase_status = price_increase_amplitude
                    break
            else:
                break
        if not increase_status:
            logger.info(f'{self.name} 5分钟粒度，价格涨幅小于-0.5% {price_increase_amplitude}')
        return increase_status


    # def short_window_amplitude(self, amp_10unit_value, res, normal_k_length):
    #     """
    #     最近8-10根K线（5m）的震荡指数，都大于阈值2.9，过滤
    #
    #     替换成与10单位均线的价格落差
    #     """
    #     # 将5m 最近10单位价格振幅返回要么返回False（加权）
    #     # amp_10unit_value = self.shock_amplitude(res, 10, normal_k_length)
    #     # amp_9unit_value = self.shock_amplitude(res, 10, normal_k_length)
    #     # amp_8unit_value = self.shock_amplitude(res, 10, normal_k_length)
    #     # if amp_10unit_value > 2.9 and amp_9unit_value > 2.9 and amp_8unit_value > 2.9:
    #     #     value = f'{self.name}最近几根K线震荡指数过大{amp_8unit_value}'
    #     #     logger.info(value)
    #     #     self.redis_cli.set(self.key, value, ex=2 * 5 * 60)
    #     #     return False
    #     return True

    def ma_and_priceincreased(self):
        """
        总入口
        均线形态和价格涨幅得同时满足条件才放行
        组合条件入口
        return False or 将5m 最近10单位价格振幅返回
        """
        res = self.req1d_pirces()
        # 重试超过次数会返回None
        if not res:
            return
        # 可能空列表，mainex会有这样的情况
        points = res.json()['data']['points']
        if not points:
            value = f'{self.name} 1D无数据{points}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=200*60*60)
            return
        # 可能刚发行的，还没几根K线
        points_list = []
        for key in points:
            points_list.append(key)
        if len(points_list) < 200:
            value = f'{self.name} 1D无数据{points}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=200*60*60)
            return
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        # k线的常规长度
        normal_k_length = self.candle_average_length(res)
        if not normal_k_length:
            return
        # 5分钟粒度，25单位均线走势，和均线与价格的关系，共三个条件
        price_to_25ma_distance_and_matrend = self.ma_strategy_25(res, normal_k_length)
        # 价格涨幅是否满足条件
        status_priceincreased = self.price_increased(res)
        # 99单位的均线斜率和价格到均线的偏离幅度，type：tuple (float, float)
        trend_99_amp = self.ma_99_trend_and_price(res, normal_k_length)
        # if not normal_k_length:
        #     return
        # 将5m 最近10单位价格振幅返回要么返回False（加权）
        amp_10unit_value = self.shock_amplitude(res, 10, normal_k_length)
        # 将5m 最近108单位价格振幅返回要么返回False （加权）
        amp_108unit_value = self.shock_amplitude(res, 108, normal_k_length)
        # 将5m 最近54单位价格振幅返回要么返回False（加权）
        amp_54unit_value = self.shock_amplitude(res, 54, normal_k_length)
        # 将5m 最近27单位价格振幅返回要么返回False（加权）
        amp_27unit_value = self.shock_amplitude(res, 27, normal_k_length)
        if not trend_99_amp:
            return
        if not price_to_25ma_distance_and_matrend:
            return
        if not status_priceincreased:
            return
        # # 确定不是4连阳
        # continuously_candle_increase_5m = PirceCheck(self.name,res).no_continuosly_increase_candle()
        # if not continuously_candle_increase_5m:
        #     return False
        if not amp_10unit_value:
            return
        if amp_10unit_value > 4:
            # 3单位 防止旗形发生
            amp_3unit_value = self.shock_amplitude(res, 3, normal_k_length)
            if (amp_3unit_value > 2) or (amp_10unit_value > 8):
                value = f'{self.name} 5m 10单位振幅过大 {amp_10unit_value} 3单位：{amp_3unit_value}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=5 * 60)
                return
        # # 当起涨价格偏离99ma的幅度是k线平均长度的3倍及以上 过滤
        trend_99_amp_slop, trend_99_amp_pricetoma_shockamp = trend_99_amp
        # if normal_k_length * 10 < abs(trend_99_amp_pricetoma_shockamp):
        #     value = f'{self.name} cmc起涨价格偏离99ma幅度超过k线长度的10倍以上{normal_k_length} {trend_99_amp_pricetoma_shockamp}'
        #     logger.info(value)
        #     self.redis_cli.set(self.key, value, ex=5*5*60)
        #     return False

        price_to_25ma_distance,trend_25ma_amp = price_to_25ma_distance_and_matrend
        # 25单位均线斜率不得小于-120
        if trend_25ma_amp < -120:
            value = f'{self.name}5M 加权25ma 小于 {trend_25ma_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=2*5 * 60)
            return
        # 最近108个单位的振幅是 k线平均长度的倍数
        # shock_108unit_compare_to_klen_times = round((amp_108unit_value/normal_k_length),3)
        # 最近108个单位5m振幅不得大于9倍的k线长度
        if amp_108unit_value > 40:
            value = f'{self.name} 108单位的振幅大于K线长度的9倍 {amp_108unit_value}'
            logger.info(value)
            return
        # # 计算加权均线斜率
        # trend_25ma_amp = round((trend_25ma_amp/normal_k_length)*100,2)
        # trend_99_amp_slop = round((trend_99_amp_slop/normal_k_length)*100,2)
        trend_200_amp_slop = self.ma_200_trend_and_price(res,normal_k_length)
        trend_250_amp_slop = self.ma_250_trend_and_price(res,normal_k_length)
        # 加权108震荡指数 复合了99ma的权重
        oscillationindex_108k_99ma=shock_index_computing(trend_99_amp_slop,amp_108unit_value)
        # 加权108震荡指数 复合了200ma的权重
        oscillationindex_108k_200ma=shock_index_computing(trend_200_amp_slop,amp_108unit_value)
        # 加权108震荡指数 复合了250ma的权重
        oscillationindex_108k_250ma=shock_index_computing(trend_250_amp_slop,amp_108unit_value)
        # 加权54震荡指数 复合了99ma的权重
        oscillationindex_54k_99ma=shock_index_computing(trend_99_amp_slop,amp_54unit_value)
        # 加权54震荡指数 复合了200ma的权重
        oscillationindex_54k_200ma=shock_index_computing(trend_200_amp_slop,amp_54unit_value)
        # 加权54震荡指数 复合了250ma的权重
        oscillationindex_54k_250ma=shock_index_computing(trend_250_amp_slop,amp_54unit_value)
        # 加权54震荡指数 复合了99ma的权重
        oscillationindex_27k_99ma=shock_index_computing(trend_99_amp_slop,amp_27unit_value)
        # 加权54震荡指数 复合了200ma的权重
        oscillationindex_27k_200ma=shock_index_computing(trend_200_amp_slop,amp_27unit_value)
        # # 最近8-10根 5m K线震荡指数过大
        # if not self.short_window_amplitude(amp_10unit_value,res,normal_k_length):
        #     return False
        #     def ma_trend_and_price(self, res, normal_k_length, window_size):
        ma10_trend_slop,price_to_ma10 = self.ma_trend_and_price(res, normal_k_length, 10)
        # 其实理论上阈值应该是 0.9 ，但是很多时候计算出来的值是失真的与行情实际的值不符，这里放宽条件，留给下游的ccxt处理
        if abs(price_to_ma10) > 2:
            # 为了避免 normal_k_length 过小导致对于实际的波动情况反馈失真
            if abs(price_to_ma10)*normal_k_length > 2:
                value = f'{self.name}5m 加权价格偏离10ma指数过大{price_to_ma10}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=1 * 5 * 60)
                return
        ma25_trend_slop,price_to_ma25 = self.ma_trend_and_price(res, normal_k_length, 25)
        # 理论值在0.9 - -0.5 这个范围，但是cmc数据可能失真，故这里放大范围
        if abs(price_to_ma25) > 2.9 or price_to_ma25 < -2.5:
            # 为了避免 normal_k_length 过小导致对于实际的波动情况反馈失真
            if abs(price_to_ma25)*normal_k_length > 2.9 or price_to_ma25*normal_k_length < -2.5:
                value = f'{self.name} 5m 加权价格偏离25ma指数过大{price_to_ma25}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=1 * 5 * 60)
                return
        ma99_trend_slop,price_to_ma99 = self.ma_trend_and_price(res, normal_k_length, 99)
        # ma150_trend_slop,price_to_ma150 = self.ma_trend_and_price(res, normal_k_length, 150)

        content = f"5m*10加权振幅：{amp_10unit_value};\n K线长度：{normal_k_length};" \
                  f"\n 价格偏离25ma 幅度（加权）：{price_to_25ma_distance};\n起涨价偏99ma均线幅度：{trend_99_amp_pricetoma_shockamp}\n" \
                  f"加权25ma:{trend_25ma_amp} 加权99ma:{trend_99_amp_slop}\n" \
                  f"加权200ma {trend_200_amp_slop}\n" \
                  f"加权108 200ma震荡指数{oscillationindex_108k_200ma}\n" \
                  f"加权54 200ma震荡指数{oscillationindex_54k_200ma}\n" \
                  f"加权54 250ma震荡指数{oscillationindex_54k_250ma}\n" \
                  f"250ma指数：{trend_250_amp_slop} 加权108 250ma震荡指数{oscillationindex_108k_250ma}\n" \
                  f"5m 加权价格偏离10ma指数：{price_to_ma10}\nto 25ma: {price_to_ma25}\n to 99ma {price_to_ma99}"
        # 所有级别的震荡指数绝对值都大于0.2，过滤
        if (abs(oscillationindex_108k_99ma)>0.2) and (abs(oscillationindex_108k_200ma)>0.2) \
                and (abs(oscillationindex_54k_99ma)>0.2) and (abs(oscillationindex_54k_200ma)>0.2):
            logger.info(f'{self.name}加权震荡指数同时大于0.2 {content}')
            value = '加权震荡指数同时大于0.2'
            self.redis_cli.set(self.key, value, ex=5 * 5 * 60)
            return

        # 108跨度 200ma 250ma 震荡指数同时大于0.1 并且最近54单位没有收敛 过滤
        if (abs(oscillationindex_108k_250ma)>0.1) and (abs(oscillationindex_108k_200ma)>0.1):
            if (oscillationindex_54k_200ma > 0.6*oscillationindex_108k_200ma) or\
                    (oscillationindex_54k_250ma > 0.6*oscillationindex_108k_250ma):
                value = f'{self.name} 108跨度 200ma 250ma加权震荡指数同时大于0.1 {content}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=5 * 5 * 60)
                return

        # 所有级别的震荡指数绝对值都大于0.06，过滤
        if (abs(oscillationindex_54k_99ma)>0.06) and (abs(oscillationindex_54k_200ma)>0.06):
            # 防止旗形上涨被过滤
            if (abs(oscillationindex_27k_99ma) > 0.03) and (abs(oscillationindex_27k_200ma) > 0.03):
                value = f'{self.name} 54unit 99ma 200ma加权震荡指数同时大于0.06 {content}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=5 * 5 * 60)
                return
        # 4小时无大阴线
        k_strong_sta = K_strong_status(prices, 48, normal_k_length, self.name, 'cmc', '5m')
        if not k_strong_sta:
            return
        else:
            logger.info(f'{self.name}  k_strong_sta: {k_strong_sta}')
        # 1小时无大阴线
        k_strong_sta = K_strong_status(prices, 12, normal_k_length, self.name, 'cmc', '5m')
        if not k_strong_sta:
            return
        else:
            logger.info(f'{self.name}  k_strong_sta: {k_strong_sta}')
        # # if 99ma and 200ma are less than 0 in the same time filter
        # if (trend_99_amp_slop < 0) and (trend_200_amp_slop < 0):
        #     logger.info(f'{self.name}99均线与200均线同时小于0 {content}')
        #     value = '99均线与200均线同时小于0'
        #     self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
        #     return False
        # # 当上升或下跌趋势震荡指数绝对值大于0.2 过滤
        # if (abs(trend_99_amp_slop)>20) and (abs(oscillationindex_108k_99ma)>0.2):
        #     value = f'{self.name}单边行情下，震荡指数过大{oscillationindex_108k_99ma}'
        #     logger.info(value)
        #     self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
        #     return False

        if (trend_250_amp_slop < -150) or (trend_250_amp_slop > 600):
            value = f'{self.name}250ma趋势异常{trend_250_amp_slop}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return
        if abs(oscillationindex_108k_200ma) > 0.37:
            value = f'{self.name}108 200ma 震荡指数大于0.38 {oscillationindex_108k_200ma}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return
        if oscillationindex_108k_250ma > 0.4:
            value = f'{self.name}108 250ma 震荡指数大于0.4 {oscillationindex_108k_250ma}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return
        if abs(oscillationindex_54k_200ma) > 0.2:
            value = f'{self.name}加权54 200ma震荡指数大于0.2 {oscillationindex_54k_200ma}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return

        if trend_200_amp_slop > 700:
            value = f'{self.name}加权200ma大于700 {trend_200_amp_slop}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return

        if trend_99_amp_slop < -100:
            value = f'{self.name}5M 99个单位均线下行速度快于 -100 {trend_99_amp_slop}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
            return
        return content,normal_k_length,trend_99_amp_pricetoma_shockamp

    def ma_99_trend_and_price(self, res, normal_k_length):
        """
        99单位的均线趋势应该要大于某个阈值
        计算起涨的价格和99单位均线的落差
        """
        points = res.json()['data']['points']
        # 总数量约为250个
        window_size = 99
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        numbers_series = pd.Series(prices)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))

        # a_p_num = 0
        # for average_price in new_ma_list:
        #     a_p_num += 10
        #     # 因为99单位的均线极其的平滑，相邻的两个单位之间几乎看不出价差，需要10单位间距进行计算
        #     increase_amplitude = ((average_price - new_ma_list[a_p_num])/new_ma_list[a_p_num])*100
        #     logger.info(f'{self.name} 5分钟粒度，99单位均线趋势：{increase_amplitude}%')
        #     return increase_amplitude
        if len(new_ma_list) < 31:
            increase_amplitude = 0
            logger.warning(f'99均线统计异常，没有足够的价格点：{points}')
        else:
            # 计算均线趋势 不得小于-0.03
            # 因为99单位的均线极其的平滑，相邻的两个单位之间几乎看不出价差，需要10单位间距进行计算
            increase_amplitude = ((new_ma_list[0] - new_ma_list[10]) / new_ma_list[10]) * 100
            increase_amplitude = round(increase_amplitude,3)
            logger.info(f'{self.name} 5分钟粒度，99单位均线趋势：{increase_amplitude}%')
        # if increase_amplitude < -0.03:
        #     value = f'{self.name}5M 99个单位均线下行并且速度快于 -0.03% {increase_amplitude}'
        #     self.redis_cli.set(self.key, value, ex=8 * 5 * 60)
        #     return False
        # 加权斜率
        trend_slop = round((increase_amplitude / normal_k_length) * 100, 2)
        # 计算起涨的价格与99ma的落差
        # 起涨时的价格
        start_increase_before_price = prices[-2]
        # 起涨时的99ma均线价格
        start_increase_before_99ma_price = moving_averages_list[-2]
        # 偏离的幅度(加权)
        price_to_ma_shock_amplitude = ((start_increase_before_price-start_increase_before_99ma_price)/start_increase_before_99ma_price)*100
        price_to_ma_shock_amplitude = round(price_to_ma_shock_amplitude/normal_k_length,3)
        # 返回加权斜率 和 加权价格偏离指数
        return trend_slop,price_to_ma_shock_amplitude

    def ma_200_trend_and_price(self, res, normal_k_length):
        """
        200日加权均线（复合了k线的长度）
        """
        points = res.json()['data']['points']
        # 总数量约为250个
        window_size = 200
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        numbers_series = pd.Series(prices)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))
        # 计算斜率
        increase_amplitude = ((new_ma_list[0] - new_ma_list[36]) / new_ma_list[36]) * 100
        increase_amplitude = round(increase_amplitude, 3)

        # # 计算起涨的价格与99ma的落差
        # # 起涨时的价格
        # start_increase_before_price = prices[-2]
        # # 起涨时的99ma均线价格
        # start_increase_before_99ma_price = moving_averages_list[-2]
        # # 偏离的幅度
        # price_to_99ma_shock_amplitude = ((
        #                                              start_increase_before_price - start_increase_before_99ma_price) / start_increase_before_99ma_price) * 100
        # price_to_99ma_shock_amplitude = round(price_to_99ma_shock_amplitude, 3)
        # 返回趋势斜率和价格偏离99ma的幅度 type：float
        # 加权斜率
        trend_200_amp_slop = round((increase_amplitude/normal_k_length)*100,2)
        return trend_200_amp_slop

    def ma_250_trend_and_price(self, res, normal_k_length):
        """
        250日加权均线（复合了k线的长度）
        """
        points = res.json()['data']['points']
        # 总数量约为280个
        window_size = 250
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        numbers_series = pd.Series(prices)
        windows = numbers_series.rolling(window_size)
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))
        # 计算斜率 列表长度约为30
        increase_amplitude = ((new_ma_list[0] - new_ma_list[-1]) / new_ma_list[-1]) * 100
        increase_amplitude = round(increase_amplitude, 3)

        # # 计算起涨的价格与99ma的落差
        # # 起涨时的价格
        # start_increase_before_price = prices[-2]
        # # 起涨时的99ma均线价格
        # start_increase_before_99ma_price = moving_averages_list[-2]
        # # 偏离的幅度
        # price_to_99ma_shock_amplitude = ((
        #                                              start_increase_before_price - start_increase_before_99ma_price) / start_increase_before_99ma_price) * 100
        # price_to_99ma_shock_amplitude = round(price_to_99ma_shock_amplitude, 3)
        # 返回趋势斜率和价格偏离99ma的幅度 type：float
        # 加权斜率
        trend_200_amp_slop = round((increase_amplitude / normal_k_length) * 100, 2)
        return trend_200_amp_slop

    def real_price_to_ma_compilizationd(self, start_increase_before_price, start_increase_before_ma_price, normal_k_length):
        """
        cmc数据不是很精准为了确保cmc数据精准，不失真，在计算价格距离10ma 和 25ma的时候；计算两个价格点，择小录用
        start_increase_before_price: 起涨时的价格
        start_increase_before_ma_price: 起涨时的ma均线价格
        """
        # 计算起涨的价格与ma的落差
        # 偏离的幅度(加权)
        price_to_ma_shock_amplitude = ((start_increase_before_price-start_increase_before_ma_price)/start_increase_before_ma_price)*100
        price_to_ma_shock_amplitude = round(price_to_ma_shock_amplitude/normal_k_length,3)
        return price_to_ma_shock_amplitude

    def ma_trend_and_price(self, res, normal_k_length, window_size):
        """
        计算均线加权斜率 和 加权价格偏离均线的指数(绝对值)
        如果是10ma，均线用2个单位的长度计算
        如果是25ma，均线用5个单位的长度计算
        """
        points = res.json()['data']['points']
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
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
        trend_amp_slop = round((increase_amplitude / normal_k_length) * 100, 2)

        # 计算起涨的价格与ma的落差
        ptm_point1 = self.real_price_to_ma_compilizationd(prices[-1],moving_averages_list[-1],normal_k_length)
        ptm_point2 = self.real_price_to_ma_compilizationd(prices[-2],moving_averages_list[-2],normal_k_length)
        price_to_ma_shock_amplitude = min([ptm_point1,ptm_point2])
        # 加权趋势 和 价格偏离均线的加权幅度
        return trend_amp_slop,price_to_ma_shock_amplitude

    def shock_amplitude(self, res, window_lenght, normal_k_length):
        """
        最近window_lenght根k线最高价到最低价的振幅不能大于某个阈值
        此判断条件应该放在价格涨幅判断之后进行
        如果能过关返回True，需要被滤掉返回False
        """
        points = res.json()['data']['points']
        # 总数量约为250个
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        # now_price = prices[-1]
        # # 价格涨幅
        # price_increase_amp = ((now_price-prices[-2])/prices[-2])*100
        # price_increase_amp = abs(price_increase_amp)
        # 剔除统计区间内的价格（干扰项）
        prices.pop()
        num = 0
        new_prices = []
        for p in list(reversed(prices)):
            num += 1
            if num > window_lenght:
                break
            else:
                new_prices.append(p)
        # window_lenght*5m内价格振幅
        price_shock_amp = ((max(new_prices)-min(new_prices))/min(new_prices))*100
        # 区间涨幅
        unilateral_market_priceshock_amp = ((new_prices[0] - new_prices[-1]) / new_prices[-1]) * 100
        # 判断是否是单边行情的指数
        increased_abs_to_amp_ratio = abs(unilateral_market_priceshock_amp) / price_shock_amp
        if unilateral_market_priceshock_amp < 0:
            # 单边下跌的幅度大于振幅的0.3倍，且单边幅度大于3倍的k线长度 认为是单边下跌趋势
            if increased_abs_to_amp_ratio > 0.3 and (abs(unilateral_market_priceshock_amp)/3 > normal_k_length):
                logger.info(f'{self.name} 单边下跌{increased_abs_to_amp_ratio}')
                # 单边下跌，振幅豁免系数0.2
                price_shock_amp_excellent = price_shock_amp*0.2
            else:
                price_shock_amp_excellent = price_shock_amp
        else:
            # 108单位 和 54单位 的针对上涨不做倍乘处理(只对10单位做倍乘)
            if window_lenght > 10:
                # 单边行情的涨幅 大于振幅的0.3倍，且单边幅度大于3倍的k线长度  认为是单边上涨趋势
                if unilateral_market_priceshock_amp > (price_shock_amp*0.3)  and (abs(unilateral_market_priceshock_amp)/3 > normal_k_length):
                    # 4.5 - 9小时的单边趋势，认为这种的震荡是优良震荡，给予一定的震荡豁免，乘系数 0.4
                    price_shock_amp_excellent = price_shock_amp*0.4
                else:
                    price_shock_amp_excellent = price_shock_amp
            else:
                # 小于等于10单位做倍乘
                # 单边行情的涨幅 大于振幅的0.3倍，且单边幅度大于3倍的k线长度  认为是单边上涨趋势
                if unilateral_market_priceshock_amp > (price_shock_amp*0.3) and (abs(unilateral_market_priceshock_amp)/3 > normal_k_length):
                    price_shock_amp_excellent = price_shock_amp*1.5
                else:
                    price_shock_amp_excellent = price_shock_amp

        # if (price_increase_amp*2 < price_shock_amp_excellent) and (price_shock_amp_excellent > 3):
        #     logger.info(f'{self.name} 5分钟粒度，最近{window_lenght}根K线振幅大于价格涨幅{price_increase_amp}的2倍且绝对值大于3 {price_increase_amp}%')
        #     return False
        # # 5m*10区间内 价格振幅不大于 0.7
        # if price_shock_amp > 0.7:
        #     value = f'{self.name} 5m 最近10根K线振幅过大{price_shock_amp}%'
        #     self.redis_cli.set(key, value, ex=5 * 5 * 60)
        #     logger.warning(value)
        #     return False
        # 加权振幅
        w_price_shock_amp = round((price_shock_amp_excellent/normal_k_length),3)
        return w_price_shock_amp


    def candle_average_length_proofreading(self, res, window):
        """
        为了避免最近的横盘震荡对K线价格反馈失真的情况出现，99单位和288单位均价择大录用
        """
        points = res.json()['data']['points']
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
        if window == 96:
            # 截取最近96*5m单位的K线价格 约占34%
            new_prices = list(reversed(prices[-96:]))
        elif window == 20:
            # 截取最近20*5m单位的K线价格
            new_prices = list(reversed(prices[-20:]))
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
        elif window == 20:
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[1:5]
        else:
            # 288单位
            kill_extremely_after = list(reversed(sorted(leng_list_origin)))[9:60]
        # 平均长度
        average_length = float(numpy.mean(kill_extremely_after))
        average_length = round(average_length,3)
        return average_length

    def candle_average_length(self, res):
        """
        计算单根K线一天内的平均长度 288个价格点
        """
        # 取最大的平均数最为整体的K线平均长度，为了规避对于某些不活跃的币种突然变得活跃了的计算偏差
        average_length_20 = self.candle_average_length_proofreading(res,20)
        average_length_99 = self.candle_average_length_proofreading(res,99)
        average_length_288 = self.candle_average_length_proofreading(res,288)
        average_length = max(average_length_20,average_length_99,average_length_288)
        if average_length < 0.25:
            # 当平均K线长度过小的时候，如果突然爆拉，也给予通过
            # 价格涨幅
            price_increased_amp = self.price_increased(res)
            if price_increased_amp:
                # # 涨幅大于1倍的平均K线长度，通过
                # if price_increased_amp > average_length:
                #     return average_length
                # 因为cmc数据有滞后性，当5m涨幅大-0.2则通过
                if price_increased_amp > -0.2:
                    return average_length
            value = f'{self.name}5m 平均k线长度太短{average_length} 涨幅：{price_increased_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=5*60)
            return
        return average_length


