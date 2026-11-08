import os
import ccxt
import logging
import time
import json
import requests
from datetime import datetime
from functools import wraps
from traceback import format_exc
# import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ETH&BTC Volume')

class Volume:
    """
    频率：每5分钟扫一次
    规则：
        近半小时净流入（大于500w U）
        近1小时净流入
        近16小时净流入
        近半小时买量递增
        近1小时买量递增
    """
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
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
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

    def filter_rules(self, diffs, volumes_increased, volumes_, symbol, prices):
        """
        过滤规则
        """
        content = None
        # 最近1小时净流入为正
        if diffs[-1] > 0 and diffs[-2] > 0:
            # 半小时买入递增
            if volumes_increased[-1] > volumes_increased[-2]:
                # 1小时买入递增
                if (volumes_increased[-1]+volumes_increased[-2]) > (volumes_increased[-3]+volumes_increased[-4]):
                    # 半小时资金净流入得大于500w U
                    if diffs[-1]*prices[-1] > 5000000:
                        # 格式化推送内容
                        content_diffs = '\n最下面数值为最新数据(30m粒度)\n净流入\n'+'\n'.join(str(d) for d in diffs)
                        content_total = '\n\n总成交\n'+'\n'.join(str(v) for v in volumes_)
                        content_increased = '\n\n买入量\n'+'\n'.join(str(vi) for vi in volumes_increased)
                        content = content_diffs + content_total + content_increased
                    else:
                        logger.info(f'{symbol} 资金净流入小于500w：{diffs[-1]*prices[-1]}')
                else:
                    logger.info(f'{symbol} 小时买入量不递增')
            else:
                logger.info(f'{symbol} 半小时买入不递增')
        else:
            logger.info(f'{symbol} 最近1小时净流入不都是为正')
        return content

    def volume_(self, candle_list, window, symbol):
        """
        window: 30 or 60
        30分钟级别和60分钟级别
        """
        all_data = []
        # 下跌的量
        volume_decreased = 0
        volume_decreased_total = 0
        # 上涨的量
        volume_increased = 0
        volume_increased_total = 0
        # 每window 总成交
        volumes_ = []
        # 每 window 买入量
        volumes_increased = []
        # 翻转列表 由近到远
        for index, p in enumerate(list(reversed(candle_list))):
            # 每 window 分钟初始化一次
            if index % window == 0:
                volume_decreased = 0
                volume_increased = 0
            # 判断涨跌
            price_increase_amplitude = ((p[4] - p[1]) / p[1]) * 100
            if price_increase_amplitude < 0:
                # 累计成交量（下跌）
                volume_decreased += p[5]
                volume_decreased_total += p[5]
            else:
                # 累计成交量（上涨）
                volume_increased += p[5]
                volume_increased_total += p[5]
            # 将当前 window 分钟的数据汇入统计列表
            if index % window == (window - 1):
                # 转成负数
                negative_volume_decreased = int(volume_decreased) * -1
                # 流出量 流入量 时间 价格
                hour_data = [
                    negative_volume_decreased,
                    int(volume_increased),
                    datetime.fromtimestamp(p[0]/1000 + 30*60).strftime('%d %H:%M'),
                    # 区间最早的一个价格点
                    list(reversed(candle_list))[index-window+1][4]
                ]
                all_data.append(hour_data)
        # 资金净流入
        diffs = []
        # 时间列表
        times = []
        # 区间时间段的开盘价列表
        prices = []
        for i in all_data:
            # 资金净流入
            volume_diff = i[1]-abs(i[0])
            diffs.append(volume_diff)
            times.append(i[2])
            prices.append(i[3])
            # 每半小时的总成交量
            volumes_.append(i[1]+abs(i[0]))
            # 买入量
            volumes_increased.append(i[1])
        # 最近16小时净流入情况
        if volume_increased_total < volume_decreased_total:
            logger.info(f'{symbol} 最近16小时买入量小于卖出量：{volume_increased_total} {volume_decreased_total}')
            return
        # 翻转列表，由远到近
        diffs,times,prices,volumes_,volumes_increased = list(reversed(diffs)),list(reversed(times)),\
                                      list(reversed(prices)),list(reversed(volumes_)),\
                                                        list(reversed(volumes_increased))
        # 只截取最近4个时间段的数据
        diffs = diffs[-4:]
        volumes_ = volumes_[-4:]
        volumes_increased = volumes_increased[-4:]
        # 根据条件过滤 看是否需要推送
        content =  self.filter_rules(diffs, volumes_increased, volumes_, symbol, prices)
        return content

    @retry()
    def get_data(self):
        # 初始化交易所
        binance_exchange = ccxt.binance({
            'timeout': 15000,
            'enableRateLimit': True
        })
        symbol_eth = 'ETH/USDT'
        # K线数据数据获取
        olhcv_eth = binance_exchange.fetch_ohlcv(symbol_eth,limit=1000)
        if not olhcv_eth:
            raise Exception('olhcv_eth Null')
        content_eth = self.volume_(olhcv_eth, 30, 'ETH')
        # content_eth = self.volume_(olhcv_eth, 999, 'ETH')
        symbol_btc = 'BTC/USDT'
        # K线数据数据获取
        olhcv_btc = binance_exchange.fetch_ohlcv(symbol_btc,limit=1000)
        if not olhcv_btc:
            raise Exception('olhcv_btc Null')
        content_btc = self.volume_(olhcv_btc, 30, 'BTC')
        # # 绘制资金净流入走势图
        # diffs, times, prices = self.volume_(olhcv, 30)
        # plt.plot(diffs, label="buy volume")
        # # plt.plot(prices, label="price")
        # plt.ylabel("Volume")
        # plt.xlabel("Time")
        # plt.xticks(range(len(times)),times,rotation='vertical')
        # plt.legend()
        # plt.savefig('ethvolume.png')

        # 过滤不符合推送条件的
        result = {}
        for i in [content_eth, content_btc]:
            if i:
                if i == content_eth:
                    result['ETH'] = content_eth
                else:
                    result['BTC'] = content_btc
                # result.append(i)
        return result

    def alert(self, msg, title='ETHVolume'):
        """
         # 文本格式化官方文档
         https://open.larksuite.com/document/ukTMukTMukTM/uMDMxEjLzATMx4yMwETM?lang=zh-CN
         :param url: webhook地址
         :param msg: 需要发送的消息
         :return:
         """
        # 默认报警链接，也支持传参
        # url = "<LARK_WEBHOOK_ALERT>"
        url = os.getenv('LARK_WEBHOOK_ETHBTC_VOLUME', '')
        msg_list = []
        for i in msg.strip().split('\n'):
            msg_row = [
                {
                    "tag": "text",
                    "text": i.strip()
                }
            ]
            msg_list.append(msg_row)

        data = {
            "email": os.getenv('LARK_MENTION_EMAIL', ''),
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": msg_list
                    }
                }
            }
        }
        headers = {'Content-Type': 'application/json'}
        num = 0
        while True:
            try:
                requests.request("POST", url, headers=headers, data=json.dumps(data))
                break
            except:
                num += 1
            if num > 3:
                logger.info('信息发送失败')
                # logger.info()
                break

    def run(self):
        # 30分钟报警一次
        while True:
            # 字典结构
            msgs = self.get_data()
            if msgs:
                for key in msgs:
                    value = msgs[key]
                    title = key
                    # 最后一个数据是最新的数据，半小时为单位
                    self.alert(value,title=title)
                    logger.info('推送成功...')
            time.sleep(5*60)
