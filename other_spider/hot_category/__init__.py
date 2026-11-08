# from .spider import Spider
from .alert import AlertEntrance
from .history_data import HistoryVol24


def run(spidername):
    # 补充历史 vol24小时数据 （工180天）
    if spidername == 'history':
        HistoryVol24().all_coins_vol24_180data()
    else:
        AlertEntrance().run()