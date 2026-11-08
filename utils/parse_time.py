import time
import hashlib
import dateparser
import moment
from datetime import datetime
from dateparser.search import search_dates

"""通用时间解析算法"""


# md5加密
def md5(code, length=None):
    res = hashlib.md5(code.encode('utf8')).hexdigest()
    if length is None:
        return res
    else:
        return res[:length]


# 解析时间
def parse_time(time_str):
    def _search_dates(str):
        datetime = search_dates(str,
                                languages=['zh'],
                                settings={
                                    'DATE_ORDER': 'YMD',
                                    'STRICT_PARSING': True,
                                    'PREFER_DATES_FROM': 'past'
                                })
        return int(time.mktime(datetime[0][1].timetuple()))

    def _is_valid_hour_time(str):
        '''判断是否是一个有效的日期字符串'''
        try:
            time.strptime(str, '%H:%M')
            return True
        except:
            return False

    def _format_date(time_str):
        '''
            格式化时间以便可以正常解析
            1、转化 年、月、日 为 -
            2、去掉 . 为 -
        '''
        if '月' in time_str and '日' in time_str:
            time_str = time_str\
                    .replace('年', '-')\
                    .replace('月', '-')\
                    .replace('日', ' ')

        if '.' in time_str:
            time_str = time_str\
                    .replace('.', '-')
        return time_str

    time_str = _format_date(time_str)
    # 格式化时间
    if _is_valid_hour_time(time_str):
        time_str = ' '.join([
            datetime.now().strftime('%Y-%m-%d'),
            time_str
        ])

    if '刚刚' in time_str or '刚才' in time_str:
        return int(time.time() )
    elif len(time_str.split('-')) == 2 or '前' in time_str:
        date_tuple = search_dates(str(time_str))
        if date_tuple:
            return int(time.mktime(date_tuple[0][1].timetuple()) )
        else:
            parse_time = dateparser.parse(str(time_str))
            return int(time.mktime(parse_time.timetuple()) )
    else:
        timestamp = None
        try:
            timestamp = _search_dates(time_str)
        except:
            moment_time = moment.date(time_str)
            if moment_time:
                timestamp = _search_dates(moment_time.format('YYYY-M-D H:m:s'))
        finally:
            return timestamp
