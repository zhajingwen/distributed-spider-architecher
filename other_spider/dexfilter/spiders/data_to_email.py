import datetime
import logging
from pandas import DataFrame
from other_spider.dexfilter.file import path
from other_spider.dexfilter.alert.send_mail import Alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DATA TO EMAIL')

class DataTransform:
    def __init__(self):
        self.alert = Alert()

    def json_to_excel(self, data_list):
        """
        将数据格式化，写入Excel
        """
        titles = ['代币名称','所属公链','时间区间','流动池大小','涨跌幅','新增持有人','买入笔数','成交量','总市值','持有人','入金vol','金额top100地址出入金']
        base_data = {}
        for title in titles:
            base_data[title] = []
        now_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        time_interval = f'{last_date} - {now_date}'
        for data in data_list:
            base_data['代币名称'].append(data['tn'])
            base_data['所属公链'].append(data['chain'])
            base_data['时间区间'].append(time_interval)
            base_data['流动池大小'].append(int(data['pb']))
            base_data['涨跌幅'].append(f"{round(data['r24h']*100)}%")
            base_data['新增持有人'].append(data['nh'])
            base_data['买入笔数'].append(data['buy'])
            base_data['成交量'].append(int(data['vn']))
            base_data['总市值'].append(data['total_value'])
            base_data['持有人'].append(data['holders'])
            base_data['入金vol'].append(data['in_cash'])
            base_data['金额top100地址出入金'].append(data['top100change'])
        df = DataFrame(base_data)
        df.to_excel(f'{path}result.xlsx', index=True, index_label='序号')

    def send_email(self, data_list):
        """
        数据写入文件
        调用email模块发邮件
        """
        # 存在压根就没有符合条件的数据
        if data_list:
            logger.info(f'有{len(data_list)}个符合条件的币！{data_list}')
            # 先写入Excel文件
            self.json_to_excel(data_list)
            # 从文件读取数据发送email
            self.alert.run()
        else:
            logger.warning('没有符合条件的数据')
