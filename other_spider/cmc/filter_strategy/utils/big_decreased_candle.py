import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('K Strong Status')

def K_strong_status(prices_list, window, average_k_length, name, data_resource, interval):
    """
    1m:最近12m
    5m:最近4小时、1小时，48根K线的强弱关系
    interval: 1m级别或者是5m级别
    """
    # 由近到远
    new_prices = list(reversed(prices_list))
    # 上涨和下跌的K线
    decline_candles = []
    increased_candles = []
    num = 0
    for p in new_prices:
        num += 1
        # 防止越界
        if num >= len(new_prices):
            break
        # 只需要最近window根K线
        if num > window:
            break
        now_price = p
        nex_price = new_prices[num]
        price_increased_amp = round(((now_price - nex_price) / nex_price) * 100, 3)
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
    # 数据不准，放宽阈值
    if data_resource == 'cmc':
        length_multiple_threshold = 0.3
        de_to_up_multiple = 4
    else:
        length_multiple_threshold = 0.6
        de_to_up_multiple = 2
    # 最长的2根阳线得大于 length_multiple_threshold 倍的最长阴线
    decline_first = sorted(decline_candles)[-1]
    increased_first = sorted(increased_candles)[-1]
    first_status = True if increased_first > (decline_first * length_multiple_threshold) else False
    second_status = True
    if len(decline_candles) > 2 and len(increased_candles) > 2:
        decline_second = sorted(decline_candles)[-2]
        increased_second = sorted(increased_candles)[-2]
        second_status = True if increased_second > (decline_second * length_multiple_threshold) else False
        if ((not first_status) and (not second_status)) or (decline_first > increased_first * de_to_up_multiple):
            logger.info(f'{name} {window} {data_resource} K线弱，两根都小，或者下跌是上涨的{de_to_up_multiple}倍')
            return
    else:
        if (not first_status) or (decline_first > increased_first * de_to_up_multiple):
            logger.info(f'{name} {window} {data_resource} K线弱，两根都小，或者下跌是上涨的{de_to_up_multiple}倍')
            return
    if window <= 20:
        # 理想阈值是1.8，但是cmc数据不准，所以这里放宽到2，用ccxt的数据进行收紧
        if data_resource == 'cmc':
            threshold = 2
        # ccxt
        else:
            if interval == '1m':
                threshold = 3
            else:
                threshold = 1.8
        # 平均K线的阈值 0.25
        if average_k_length < 0.25:
            if interval == '1m':
                threshold = 4
            else:
                threshold = 2
        # 最长的下跌K线大于 threshold 倍的平均K线长度，过滤
        if decline_first/average_k_length > threshold:
            logger.info(f'{name} {window} {data_resource}下跌是平均K线长度的{threshold}倍以上：{decline_first} {average_k_length}')
            return
    else:
        # 最长的下跌K线大于4倍的平均K线长度，过滤
        if decline_first/average_k_length > 4:
            logger.info(f'{name} {window} {data_resource}下跌是平均K线长度的4倍以上：{decline_first} {average_k_length}')
            return
    content = f"first: {first_status}; second: {second_status}"
    return content