from .fundrasing import RaisedBio
from .trendx import Trendx

def funding_info(data):
    # fundrasing
    data = RaisedBio().combined_rasing(data)
    # 当fundrasing没有采集到数据的时候，通过trendx采集
    data = Trendx().combined_rasing(data)
    return data

