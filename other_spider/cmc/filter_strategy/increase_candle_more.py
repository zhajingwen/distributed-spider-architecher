import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('No Exsit Continuously Candle')



class PirceCheck:
    def __init__(self, name, res):
        self.name = name
        self.res = res

    def no_continuosly_increase_candle(self):
        """
        不存在连续上涨的5分钟粒度的k先；这里定义为4根
        如果真的不存在，那么就Return True; 进行下一步的过滤
        """
        points = self.res.json()['data']['points']
        # 原生的价格列表
        prices = []
        num = 0
        for point in points:
            num += 1
            price = points[point]['v'][0]
            prices.append(price)
            num = 0
        new_prices = list(reversed(prices))
        # 最近4根5分钟粒度的K线的阴阳状态
        prices_diffs = []
        for p in new_prices:
            num += 1
            if num < 5:
                # 计算5分钟k先收盘价到开盘价的价差
                price_diff = p - new_prices[num]
                prices_diffs.append(price_diff)
            else:
                break
        status = False
        # 但凡有一根阴线就通过，返回True
        for d in prices_diffs:
            if d < 0:
                status = True
        if not status:
            value = f'{self.name} 4连阳过滤'
            logger.info(value)
        return status
