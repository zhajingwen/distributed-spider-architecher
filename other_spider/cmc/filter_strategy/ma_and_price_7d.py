import logging
import time
import heapq
import numpy
import requests
from copy import deepcopy
from functools import wraps
from traceback import format_exc
import pandas as pd
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from other_spider.cmc.filter_strategy.utils.shock_index import shock_index_computing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('CMC 7D')

class Price7D:
    def __init__(self, id, name, market):
        """
        计算小时K线数据
        702个价格点(15m),175个价格点（小时）
        时间列表序列由远及近，列表-1个元素是最近一小时的数据
        每个点之间时间差15分钟
        """
        self.url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart?id={id}&range=7D'
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
    def req7d_pirces(self):
        """
        请求7天的价格数据
        """
        # price_usd = float(price_usd)
        res = requests.get(self.url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'1D状态码错误：{self.name} {res.status_code}')
        logger.info(f'{self.name} {res.status_code}: {self.url}')
        try:
            res.json()
        except:
            logger.error(f'{self.name}7日json()错误：{self.url}')
            raise Exception('res json 错误')
        return res

    def K_strong_status(self, prices_list, normal_k_length, window):
        """
        最近window根k线的强弱关系（长度上）
        """
        # 由近到远
        new_prices = list(reversed(prices_list))
        # 上涨和下跌的K线
        decline_candles = []
        increased_candles = []
        num = 0
        for p in new_prices:
            num += 1
            # 只需要最近window根小时线
            if num > window:
                break
            now_price = p
            nex_price = new_prices[num]
            price_increased_amp = round(((now_price-nex_price)/nex_price)*100,3)
            if price_increased_amp > 0:
                increased_candles.append(price_increased_amp)
            else:
                decline_candles.append(abs(price_increased_amp))
        # 无上涨的K线
        if not increased_candles:
            return
        # 无下跌
        if not decline_candles:
            return '无下跌的K线'
        # 如果最近三根K线有出现大跌的，则过滤，阈值为平均K线长度
        for index,dc in enumerate(decline_candles):
            if index < 3:
                if dc > normal_k_length:
                    value = f'{self.name} 小时K 最近{index+1}k 有大跌'
                    logger.info(value)
                    self.redis_cli.set(self.key, value, ex=1 * 60 * 60)
                    return
        # 最长的2根阳线得大于0.9倍的最长阴线
        decline_first = sorted(decline_candles)[-1]
        increased_first = sorted(increased_candles)[-1]
        first_status = True if increased_first > (decline_first * 0.9) else False
        second_status = True
        if len(decline_candles) > 2 and len(increased_candles) > 2:
            decline_second = sorted(decline_candles)[-2]
            increased_second = sorted(increased_candles)[-2]
            second_status = True if increased_second > (decline_second * 0.9) else False
            if ((not first_status) and (not second_status)) or (decline_first > increased_first * 2):
                value = f'{self.name} 小时K 最近{window}k 太弱'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=2 * 60 * 60)
                return
            else:
                logger.info(f'最长下跌k线最大上涨的倍数：{decline_first / increased_first}')
        else:
            if (not first_status) or (decline_first > increased_first * 2):
                # logger.info(f'{name} K线弱，两根都小，或者下跌是上涨的两倍')
                # return
                value = f'{self.name} 小时K 最近{window}k 太弱'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=2 * 60 * 60)
                return
            else:
                logger.info(f'最长下跌k线最大上涨的倍数：{decline_first / increased_first}')
        if window <= 10:
            # 最长的下跌K线大于1.5倍的平均K线长度，过滤
            if decline_first / normal_k_length > 1.5:
                value = f'{self.name} 下跌是平均K线长度的1.5倍以上：{decline_first / normal_k_length}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=2*60*60)
                return
        # window == 20
        else:
            df_to_akl_times = decline_first / normal_k_length
            # 最长的下跌K线较大，过滤
            if (df_to_akl_times>2) or (df_to_akl_times>1.5 and decline_first>increased_first):
                value = f'{self.name} 下跌是平均K线长度的2倍以上：{decline_first / normal_k_length}'
                logger.info(value)
                self.redis_cli.set(self.key, value, ex=2*60*60)
                return
        content = f"first: {first_status}; second: {second_status} decline_first:{decline_first} normal_k_length:{normal_k_length}"
        return content

    def run(self):
        """
        总入口
        均线形态和价格涨幅得同时满足条件才放行
        组合条件入口
        return False or 将5m 最近10单位价格振幅返回
        """
        res = self.req7d_pirces()
        # 重试超过次数会返回None
        if not res:
            logger.info(f'{self.name} 响应体为空: {self.url}')
            return
        # 可能空列表，mainex会有这样的情况
        points = res.json()['data']['points']
        if not points:
            value = f'{self.name} 7D无数据{points}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=200*60*60)
            return
        # 可能刚发行的，还没几根K线
        prices_list = []
        for key in points:
            price = points[key]['v'][0]
            prices_list.append(price)
        reversed_prices_list = list(reversed(prices_list))
        num = 0
        # 由近及远的小时价格点
        price_1h_list_reversed = []
        for p in reversed_prices_list:
            if num % 4 == 0:
                price_1h_list_reversed.append(p)
            num += 1
        if len(price_1h_list_reversed) < 150:
            value = f'{self.name} 7D无数据'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=200*60*60)
            return
        # 常规时间线的小时价格点
        price_1h_list = list(reversed(price_1h_list_reversed))

        # k线的常规长度
        normal_k_length = self.candle_average_length(price_1h_list)
        # 150单位的均线斜率（加权）,当前价对应的均线价
        ma_150_slop_weighted,ma150_now_point_price = self.ma_trend(price_1h_list, normal_k_length, 150)
        # 99单位的均线斜率（加权）,当前价对应的均线价
        ma_99_slop_weighted,ma99_now_point_price = self.ma_trend(price_1h_list, normal_k_length, 99)
        # 50单位的均线斜率（加权）,当前价对应的均线价
        ma_50_slop_weighted,ma50_now_point_price = self.ma_trend(price_1h_list, normal_k_length, 50)
        # 25单位的均线斜率（加权）,当前价对应的均线价
        ma_25_slop_weighted,ma25_now_point_price = self.ma_trend(price_1h_list, normal_k_length, 25)
        # 10单位的均线斜率（加权）,当前价对应的均线价
        ma_10_slop_weighted,ma10_now_point_price = self.ma_trend(price_1h_list, normal_k_length, 10)
        if ma_150_slop_weighted < -40:
            value = f'{self.name} 小时 150ma 小于-40：{ma_150_slop_weighted}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=8*60*60)
            return
        # 加权震荡指数 34单位
        shock_index_34 = self.shock_amplitude(prices_list, 34, normal_k_length, ma_150_slop_weighted)

        if abs(shock_index_34) > 0.055:
            value = f'{self.name} 小时 34k 震荡指数大于0.055：{shock_index_34}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=2*60*60)
            return
        # 最近10根k线强弱关系
        k_strong_sta_10 = self.K_strong_status(price_1h_list, normal_k_length, 10)
        if not k_strong_sta_10:
            return
        # 最近20根k线强弱关系
        k_strong_sta_20 = self.K_strong_status(price_1h_list, normal_k_length, 20)
        if not k_strong_sta_20:
            return
        departure_150ma_amp = self.departure_ma_amp(prices_list[-1], ma150_now_point_price, normal_k_length)
        if departure_150ma_amp > 10:
            value = f'{self.name} 小时 当前价偏离150ma均线过大：{departure_150ma_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=5*60*60)
            return
        # if 99ma if under 150ma compute the waterfall weighted
        # if it's value more than threshold filter
        ma99_to_ma150_waterfall = ''
        if ma99_now_point_price < ma150_now_point_price:
            ma99_to_ma150_waterfall =(ma150_now_point_price - ma99_now_point_price)/ma99_now_point_price
            ma99_to_ma150_waterfall = round((ma99_to_ma150_waterfall/normal_k_length),3)
        # # 50小时震荡区间高位过滤 （超过50%）
        # price_divia_to99ma = self.price_distance_to_ma(price_1h_list)
        # if not price_divia_to99ma:
        #     return False
        # 偏离25单位均线的幅度
        departure_25ma_amp = self.departure_ma_amp(prices_list[-1], ma25_now_point_price, normal_k_length)
        # 偏离10单位均线的幅度
        departure_10ma_amp = self.departure_ma_amp(prices_list[-1], ma10_now_point_price, normal_k_length)
        if departure_10ma_amp > 1.5:
            value = f'{self.name} 小时 当前价偏离10ma均线过大：{departure_10ma_amp}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=30*60)
            return
        # 加权震荡指数 5单位
        shock_index_5 = self.shock_amplitude(prices_list, 5, normal_k_length, ma_150_slop_weighted)
        if abs(shock_index_5) > 0.045:
            value = f'{self.name} 小时 5单位振幅过大：{shock_index_5}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=30*60)
            return
        # 加权震荡指数 10单位
        shock_index_10 = self.shock_amplitude(prices_list, 10, normal_k_length, ma_150_slop_weighted)
        if abs(shock_index_10) > 0.08:
            value = f'{self.name} 小时 10单位振幅过大：{shock_index_10}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=30*60)
            return
        # 过滤4连阳
        if self.four_continuosly_increased(prices_list):
            value = f'{self.name} 4连阳'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=60*60)
            return
        content = f'\n小时数据：\n150单位的均线斜率: {ma_150_slop_weighted}\n34H加权震荡指数: {shock_index_34}\n' \
                  f'最近10根k线强弱关系: {k_strong_sta_10} {k_strong_sta_20}\n当前价偏离150ma1H的幅度：{departure_150ma_amp}  ' \
                  f' to25ma: {departure_25ma_amp}  to10ma: {departure_10ma_amp}\n' \
                  f'99ma-150ma waterfall: {ma99_to_ma150_waterfall}\n' \
                  f'1H震荡指数 5U: {shock_index_5} 10U：{shock_index_10}'
        return content

    def ma_trend(self, prices_list, average_k_length, window_size):
        """
        总价格点：175个
        小时K线，150ma,99ma
        """
        # window_size = 150
        numbers_series = pd.Series(prices_list)
        windows = numbers_series.rolling(window_size)
        # 剔除空值
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))
        # 当前价对应的均线价格
        now_point_price = new_ma_list[0]

        compute_interval = 20
        if window_size == 10:
            compute_interval = 2
        if window_size == 25:
            compute_interval = 5
        # 防止越界
        if len(new_ma_list)-1 < compute_interval:
            compute_interval = len(new_ma_list)-1
        # 一共就25个点，20单位间距进行计算
        increase_amplitude = ((new_ma_list[0] - new_ma_list[compute_interval]) / new_ma_list[compute_interval]) * 100
        increase_amplitude = round(increase_amplitude,3)
        amp_slop = round((increase_amplitude/average_k_length)*100,2)
        logger.info(f'{self.name} 1H {window_size}ma加权斜率：{amp_slop}')
        return amp_slop,now_point_price

    def shock_amplitude(self, prices_list, window_lenght, normal_k_length, ma_slop):
        """
        prices_list：702个15m时间差价格点
        共702个价格点，这里故意不用小时粒度的，因为可能会漏掉某些极值，
        上影线下影线之类的，故采用15分钟粒度的，15*4*34，这个区间价格振幅来算34*1H K线的振幅
        价格振幅
        """
        prices = deepcopy(prices_list)
        # now_price = prices[-1]
        # 剔除统计区间内的价格（干扰项）
        prices.pop()
        num = 0
        new_prices = []
        for p in list(reversed(prices)):
            num += 1
            if num > window_lenght*4:
                break
            else:
                new_prices.append(p)
        # window_lenght*1H内价格振幅
        price_shock_amp = ((max(new_prices)-min(new_prices))/min(new_prices))*100
        price_shock_amp = round(price_shock_amp,3)
        # 单边涨幅
        unilateral_market_priceshock_amp = ((new_prices[0] - new_prices[-1]) / new_prices[-1]) * 100

        # 判断是否是单边行情的指数
        increased_abs_to_amp_ratio = abs(unilateral_market_priceshock_amp) / price_shock_amp
        price_shock_amp_excellent = price_shock_amp
        if unilateral_market_priceshock_amp < 0:
            # 单边下跌的幅度大于振幅的0.3倍，且单边幅度大于3倍的k线长度  认为是单边下跌趋势
            # 单边下跌的行情，振幅乘以系数2/3
            if increased_abs_to_amp_ratio > 0.3 and (abs(unilateral_market_priceshock_amp)/3 > normal_k_length):
                if window_lenght <= 12:
                    # 单边下跌，振幅豁免系数0.5
                    price_shock_amp_excellent = abs(price_shock_amp)*0.5
                else:
                    # 单边下跌，振幅豁免系数2/3
                    price_shock_amp_excellent = abs(price_shock_amp)*(2/3)
        # 单边上涨
        else:
            # 34单位 的针对上涨不做倍乘处理(只对10单位做倍乘)
            if window_lenght > 10:
                # 单边行情的涨幅 大于振幅的0.3倍，且单边幅度大于3倍的k线长度  认为是单边上涨趋势
                if increased_abs_to_amp_ratio > 0.3 and (abs(unilateral_market_priceshock_amp)/3 > normal_k_length):
                    # 34小时的单边趋势，认为这种的震荡是优良震荡，给予一定的震荡豁免，乘系数 0.2
                    price_shock_amp_excellent = price_shock_amp*0.2
                    logger.info(f'{self.name} 34hour 单边')
                    # # 大单边趋势
                    # if increased_abs_to_amp_ratio > 0.5:
                    #     # 34小时的大单边，为了让震荡的值看起来合理，乘以0.05
                    #     price_shock_amp_excellent = price_shock_amp * 0.05
            else:
                # 上涨幅度大于3倍的k线长度 认为是单边
                if abs(unilateral_market_priceshock_amp)/3 > normal_k_length:
                    # 10单位 单边 做分级倍乘
                    if increased_abs_to_amp_ratio > 0.3:
                        price_shock_amp_excellent = round(price_shock_amp * 3, 3)
                    elif increased_abs_to_amp_ratio > 0.4:
                        price_shock_amp_excellent = round(price_shock_amp * 4, 3)
                    elif increased_abs_to_amp_ratio > 0.5:
                        price_shock_amp_excellent = round(price_shock_amp * 5, 3)
                    elif increased_abs_to_amp_ratio > 0.6:
                        price_shock_amp_excellent = round(price_shock_amp * 6, 3)
                    else:
                        price_shock_amp_excellent = round(price_shock_amp * 10, 3)
        # 加权振幅
        w_price_shock_amp = round((price_shock_amp_excellent/normal_k_length),5)
        # 加权震荡指数（复合和均线）
        oscillationindex_weighted_to_ma = shock_index_computing(ma_slop, w_price_shock_amp)
        return oscillationindex_weighted_to_ma

    def candle_average_length(self, prices_list):
        """
        计算单根K线7天内，最近96小时内的平均长度
        """
        # 截取最近96*1H单位的K线价格 约占34%
        new_prices = list(reversed(prices_list[-96:]))
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
        kill_extremely_after_96 = list(reversed(sorted(leng_list_origin)))[3:23]
        kill_extremely_after_20 = list(reversed(sorted(leng_list_origin[:20])))[1:5]
        kill_extremely_after_10 = list(reversed(sorted(leng_list_origin[:10])))[:2]
        # 平均长度
        average_length_96 = float(numpy.mean(kill_extremely_after_96))
        average_length_20 = float(numpy.mean(kill_extremely_after_20))
        average_length_10 = float(numpy.mean(kill_extremely_after_10))
        average_length = round(max(average_length_96,average_length_20,average_length_10),3)
        return average_length

    def departure_ma_amp(self, now_price, ma_now_point_price, normal_k_length):
        """
        起涨价价格偏离均线的幅度（加权）
        算法：amp = round(((now_price - ma_now_point_price)/ma_now_point_price)*100,4)
        ，在此基础上复合K线的长度，w_amp = amp/normal_k_length
        """
        amp = round(((now_price - ma_now_point_price)/ma_now_point_price)*100,4)
        w_amp = abs(round(amp/normal_k_length,3))
        return w_amp

    def price_distance_to_ma(self, prices_list):
        """
        是否在价格震荡区间的中间靠下的位置
        当前价到均线的落差处于最近一段时间什么水平？
        """
        window_size = 99
        numbers_series = pd.Series(prices_list)
        windows = numbers_series.rolling(window_size)
        # 剔除空值
        moving_averages = windows.mean().dropna()
        # 移动平均线的价格列表
        moving_averages_list = moving_averages.tolist()
        # 逆转均线，从近到远
        new_ma_list = list(reversed(moving_averages_list))
        # 当前价对应的均线价格
        now_point_price = new_ma_list[0]
        new_prices_list = list(reversed(prices_list))
        # 当前价格到均线的落差
        diviation_now = new_prices_list[0]-now_point_price
        num = 0
        price_deviation_list = []
        for ma_point in new_ma_list:
            if num > 49:
                break
            # 价格到99单位均线的落差
            p_d_to_ma = abs(new_prices_list[num]-ma_point)
            price_deviation_list.append(p_d_to_ma)
            num += 1
        # 统计区间内，最大的价格落差
        max_diviation = max(price_deviation_list)
        if diviation_now > (max_diviation/2):
            value = f'{self.name} 1H K 处于震荡区间的高位：{diviation_now}'
            logger.info(value)
            self.redis_cli.set(self.key, value, ex=5*60*60)
            return
        # 当前的落差处于什么位置
        diviation_now_station = round(diviation_now/max_diviation,3)
        return diviation_now_station

    def four_continuosly_increased(self, prices_list):
        """
        连续4根K线上涨返回True
        """
        num = 0
        new_prices = []
        for p in list(reversed(prices_list)):
            num += 1
            if num == 1:
                new_prices.append(p)
            else:
                if num % 4 == 0:
                    new_prices.append(p)
        four_unit_increased_list = []
        num = 0
        # 小时价格点
        for index,p in enumerate(new_prices):
            num += 1
            price_increased_amplitude = ((p - new_prices[index+1])/new_prices[index+1])
            four_unit_increased_list.append(price_increased_amplitude)
            if num > 3:
                break
        all_positive = all(num > 0 for num in four_unit_increased_list)
        return all_positive