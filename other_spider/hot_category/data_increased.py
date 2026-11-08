import logging
from utils.rds import DataUtils
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('History Data')

class Increased:
    def __init__(self):
        self.rds = DataUtils()
        self.table_coin = 'hot_category_jack_coin'
        self.table_cate = 'hot_category_jack_cate'
        # 单日板块总市值上涨告警的阈值
        self.oneday_increased_threshold = 0.05

    def gen_dates(self):
        """
        生成需要查询的日期
        """
        # 获取当前日期
        current_date = datetime.now()
        current_date_str = current_date.strftime("%Y-%m-%d")

        # 计算1天前的日期
        one_day_ago = current_date - timedelta(days=1)
        one_day_ago_str = one_day_ago.strftime("%Y-%m-%d")

        # 计算2天前的日期
        two_days_ago = current_date - timedelta(days=2)
        two_days_ago_str = two_days_ago.strftime("%Y-%m-%d")

        # 计算3天前的日期
        three_days_ago = current_date - timedelta(days=3)
        three_days_ago_str = three_days_ago.strftime("%Y-%m-%d")
        dates = [current_date_str, one_day_ago_str, two_days_ago_str, three_days_ago_str]
        return dates

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num / 1000000000), 2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num / 1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    def calculate_between_histroy(self):
        """
        计算历史数据变化的幅度，并存于局部变量中：json
        """
        dates = self.gen_dates()
        # dates = ['2024-03-07', one_day_ago_str, two_days_ago_str, three_days_ago_str]
        # 倒序，从远到近
        dates = list(reversed(dates))
        the_older_data = {}
        categories_all_diff_data = {}
        for index, d in enumerate(dates):
            sql = f'SELECT category,fdv FROM hot_category_jack_cate where spider_date={repr(d)};'
            # 只要当前日期（d）查询无结果，那么就跳过
            data = self.rds.select(sql)
            if not data:
                continue
            # logger.info(f'{d} {data}')
            # 如果当前日期（d）有结果，那么将会返回一个包含JSON的列表
            for item in data:
                category = item['category']
                # 上一天的数据（ for index, d in enumerate(dates): 首次循环 the_older_data为空，那么意味着，首条数据增幅一定是0）
                # 当首次计算每日增幅的时候，第一条数据给一个 0 初始值；后天在列表中剔除即可
                the_old_fdv = the_older_data.get(category, item['fdv'])
                diff = item['fdv'] - the_old_fdv
                diff_percent = round(diff/the_old_fdv, 2)
                diff_data = {
                    "diff": self.num_transform(diff),
                    "diff_percent": diff_percent,
                    'fdv':item['fdv']
                }
                if category not in categories_all_diff_data:
                    categories_all_diff_data[category] = [diff_data]
                else:
                    categories_all_diff_data[category].append(diff_data)
                # 将当前的数据存入历史数据容器
                the_older_data[category] = item['fdv']
        return  categories_all_diff_data


    def rule_oneday(self, diff_list, alert_data, c):
        """
        diff_list: 存放一个板块涨幅数据的列表[json]
        判断最近一天的涨幅是否能过筛选
        """
        the_newest_one = diff_list[-1]
        the_newest_one_diff_percent = the_newest_one['diff_percent']
        the_newest_one_diff = the_newest_one['diff']
        fdv = self.num_transform(the_newest_one['fdv'])
        # 单日增幅大于阈值，那么就触发告警
        if the_newest_one_diff_percent > self.oneday_increased_threshold:
            # 涨幅格式化
            increased_content = f'+{the_newest_one_diff_percent * 100}%'
            alert_data[c] = f'市值{fdv} 昨日增长{the_newest_one_diff}({increased_content})'
        return alert_data

    def sort_onde_day(self, categories_all_diff_data):
        """
        对最近一日总市值增幅从高到低进行排序
        """
        new_categroies_increased = {}
        for category in categories_all_diff_data:
            new_categroies_increased[category] = categories_all_diff_data[category][-1]
        sorted_dict = list(reversed(sorted(new_categroies_increased.items(), key=lambda x: x[1]["diff_percent"])))
        alert_content = '当日板块总市值涨幅排行：\n\n'
        for item in sorted_dict:
            category = item[0]
            fdv = item[1]['fdv']
            fdv = self.num_transform(fdv)
            diff = item[1]['diff']
            increased_percent = item[1]['diff_percent']*100
            # 涨幅格式化
            if increased_percent > 0:
                increased_percent_content = f'+{increased_percent}%'
            else:
                increased_percent_content = f'{increased_percent}%'
            # # Pow: 市值1.1B 昨日增长0.1B(+9%)
            row = f'{category}：市值{fdv}  昨日增长{diff}({increased_percent_content})\n'
            alert_content += row
        return alert_content

    def comparation_data(self):
        """
        比对数据，算出涨幅，返回符合条件的数据
        """
        # 获取查询日期
        dates = self.gen_dates()
        # 拿到历史数据比对结果（涨跌幅）
        categories_all_diff_data = self.calculate_between_histroy()
        sorted_oneday_increased_alert_content = self.sort_onde_day(categories_all_diff_data)
        alert_data = {}
        # 对统计结果进行规则过滤
        for c in categories_all_diff_data:
            diff_list = categories_all_diff_data[c]
            # 最近3日有一日或者多日无数据的情况
            if len(diff_list) < len(dates):
                # 记录最近一日涨幅满足条件的板块
                alert_data = self.rule_oneday(diff_list, alert_data, c)
            # 最近3日数据库都有数据
            else:
                # 连续3日增幅都必须大于0，那么才出发告警
                alert_status = True
                # diff_list[1:]表示最近3日的市值增幅
                for diff in diff_list[1:]:
                    diff_percent = diff['diff_percent']
                    if diff_percent <= 0:
                        alert_status = False
                if alert_status:
                    diff_content_list = []
                    for d_json in diff_list[1:]:
                        diff_c_row = f"{self.num_transform(d_json['fdv'])}(+{d_json['diff_percent']*100}%)"
                        diff_content_list.append(diff_c_row)
                    # 每个板块，携带3日上涨的具体涨幅
                    increased_alert_category_content = '--->'.join(diff_content_list)
                    alert_data[c] = f'总市值连续3日上涨: --->{increased_alert_category_content}'
                # 对该条件中，有三日数据，但是不是三日连涨的，仍然要做一个最近一日涨幅大于5%的判断
                else:
                    # 记录最近一日涨幅满足条件的板块
                    alert_data = self.rule_oneday(diff_list, alert_data, c)
        return alert_data,sorted_oneday_increased_alert_content

    def alert_content(self):
        content_tuple = self.comparation_data()
        return content_tuple



