import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('WeekStrong')



class WeekCandle:
    def __init__(self, name):
        self.name = name

    def gen_candle(self, data, timeframe=60):
        """
        data里面数据为周线数据，默认粒度是15分钟
        timeframe: 小时粒度的蜡烛图  60表示一小时k线为默认参数
        """
        points = data['data']['points']
        h_k_price_1 = []
        h_k_price_2 = []
        h_k_price_3 = []
        time_interval = (7*24*60*60)/3
        time_t_next = None
        # 时间序列往后是增长的
        for point in points:
            time_t = int(point)
            # # 忽略最近24小时的价格
            # if time_t > (int(time.time())-24*60*60):
            #     continue
            if time_t_next:
                if time_t < time_t_next:
                    continue
            price = points[point]['v'][0]
            for p in points:
                time_t_next = int(p)
                # 如果是上涨趋势，后一刻的价格一定比前一刻的价格高
                if time_t_next - time_t >= timeframe * 60:
                    price_next = points[p]['v'][0]
                    diff = price_next - price
                    if time_t_next < (int(time.time())-time_interval*2):
                        h_k_price_1.append(diff)
                    elif time_t_next < (int(time.time())-time_interval*1):
                        h_k_price_2.append(diff)
                    else:
                        h_k_price_3.append(diff)
                    break
        return h_k_price_1,h_k_price_2,h_k_price_3

    def maopao(self,arr):
        """
        冒泡排序
        """
        for j in range(len(arr)):
            # 拿初始位置的元素往后面和所有元素比较，遇到更大等就把更大的往后挤
            # len(arr)-j   j个元素已经冒到最末了，只需要比对前len(arr)-j个元素
            for i in range(len(arr) - j - 1):
                # print(j)
                if abs(arr[i]) > abs(arr[i + 1]):
                    # 交换位置
                    arr[i + 1], arr[i] = arr[i], arr[i + 1]
            # 这一轮结束后会生成一个全新等arr，直到把前面最大的挤到最后一个元素
            # print(arr)
        return arr

    def price_rise_num_proption(self,arr):
        """
        获取蜡烛图变化幅度较大中，上涨的个数所占的比重
        """
        # 单个阶段的全部小时图中，只取k线长度排名靠前的40%
        index_start = int(len(arr)*0.4)
        # 长的在后面，所以取靠后的
        new_arr = arr[-index_start:]
        # 计算上涨的个数
        num = 0
        for i in new_arr:
            if i>0:
                num += 1
        proption = num/len(new_arr)
        return proption

    def price_rise_largest_proption(self,arr):
        """
        最长的那几根K线上涨的应该超过60%
        后面考虑调整到70%
        """
        # 单个阶段的全部小时图中，只取k线长度排名靠前的40%
        index_start = int(len(arr)*0.2)
        # 长的在后面，所以取靠后的
        new_arr = arr[-index_start:]
        # 计算上涨的个数
        num = 0
        for i in new_arr:
            if i>0:
                num += 1
        proption = num/len(new_arr)
        return proption

    def timeframe_diff(self, data, timeframe):
        """
        分15、30分钟和1小时,要求不同级别的K线都得表示出强势才行
        """
        h_k_price_1,h_k_price_2,h_k_price_3 = self.gen_candle(data,timeframe)
        # 根据变化幅度排序，变化最大的在列表最后面
        h_k_price_1 = self.maopao(h_k_price_1)
        h_k_price_2 = self.maopao(h_k_price_2)
        h_k_price_3 = self.maopao(h_k_price_3)
        # 最后一个阶段最长的K线不能是跌的
        if h_k_price_3[-1] < 0:
            logger.info(f'{self.name} 周线{timeframe}分图最近2.5天出现大跌K线')
            return False
        num_p1 = self.price_rise_num_proption(h_k_price_1)
        num_p2= self.price_rise_num_proption(h_k_price_2)
        num_p3 = self.price_rise_num_proption(h_k_price_3)
        num_p3_largest = self.price_rise_largest_proption(h_k_price_3)
        if num_p3_largest < 0.6:
            logger.info(f'{self.name} 周线{timeframe}分图最近2.5天最长的几根K线上涨的占比不到60%')
            return False
        if num_p2 >= num_p1:
            if num_p3 >= num_p2:
                # 强势的应该超过半数
                if num_p3 > 0.5:
                    return True
                else:
                    logger.info(f'{self.name} 周线{timeframe}分图最近2.5天价格易跌难涨')
                    return False
            else:
                logger.info(f'{self.name} 周线{timeframe}分图最后阶段走弱')
                return False
        else:
            logger.info(f'{self.name} 周线{timeframe}分图中间阶段走弱')
            return False

    def run(self, data):
        """
        一个走切成三个阶段要一个阶段比一个阶段强，并且最后一个阶段绝对强才行
        这里的强的定义是：长K线基本是涨的
        """
        status15 = self.timeframe_diff(data,15)
        status30 = self.timeframe_diff(data,30)
        status60 = self.timeframe_diff(data,60)
        # 30 60 分K线同时都强，则强
        if status15 and status30 and status60:
            return True
        else:
            return False



