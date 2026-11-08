import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.lark_bot_response import Send
import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from other_spider.btc_gas.config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gen Graph')

class GenFileId:
    def __init__(self, id):
        self.job_id = id
        self.redis_cli = redis_cli()
        self.table_name = 'btc_gas'
        self.rds = DataUtils()
        self.send = Send(app_id, app_secret, app_name)
        self.file_name = f'{id}.png'
        self.redis_jobkey = 'btcgas:coinsadjust:{}'

    def get_histroy_gas(self, days):
        """
        从数据库读取历史gas数据
        """
        if days <= 1:
            logger.warning('用户输入的天数小于2天，无法生成图表')
            return
        start_date = (datetime.now() - timedelta(days=days - 1))
        # 获取查询起点时间0点的时间戳
        timestamp = int(start_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        sql = f'select gas from {self.table_name} where spider_time >= {timestamp};'
        data = self.rds.select(sql)
        gas_list = []
        if data:
            for item in data:
                gas = item['gas']
                gas_list.append(gas)
        else:
            return
        return gas_list

    def gen_graph(self, days):
        """
        根据历史数据绘制折线图并且保存
        """
        gas_list = self.get_histroy_gas(days)
        if gas_list:
            x = []
            y = []
            for index, gas in enumerate(gas_list):
                x.append(index+1)
                y.append(gas)
            # 计算变化百分比
            percentage_change = [None]  # 第一个点的变化百分比设为None
            for i in range(1, len(y)):
                change = ((y[i] - y[i - 1]) / y[i - 1]) * 100
                percentage_change.append(change)

            # 生成折线图
            plt.plot(x, y)
            plt.title(f'Recent {len(gas_list)} days')
            plt.xlabel('day')
            plt.ylabel('GAS')

            # 在每个坐标点上显示Y轴的值和变化百分比
            for i in range(len(x)):
                if percentage_change[i] is not None:
                    plt.annotate(f'{y[i]} ({int(percentage_change[i])}%)', (x[i], y[i]), textcoords="offset points",
                                 xytext=(0, 10), ha='center')
                else:
                    plt.annotate(f'{y[i]}', (x[i], y[i]), textcoords="offset points", xytext=(0, 10), ha='center')
            # 设置为整型
            plt.xticks(x)
            # 保存折线图
            plt.savefig(self.file_name)
            plt.close()

    def upload(self):
        """
        上传图片
        """
        # 创建client
        client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.ERROR) \
            .build()

        # 构造请求对象
        file = open(self.file_name, "rb")
        request: CreateImageRequest = CreateImageRequest.builder() \
            .request_body(CreateImageRequestBody.builder()
                          .image_type("message")
                          .image(file)
                          .build()) \
            .build()

        # 发起请求
        response: CreateImageResponse = client.im.v1.image.create(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.im.v1.image.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return

        # 处理业务结果
        data_str = lark.JSON.marshal(response.data, indent=4)
        data = json.loads(data_str)
        image_key = data['image_key']
        # 将image_key存入redis, 当任务相同的时候，后面就不用重复生成image_key 了
        redis_key = self.redis_jobkey.format(self.job_id)
        # image_key有效期最长24小时，故设置过期时间
        self.redis_cli.setex(redis_key, 24*60*60, image_key)
        return image_key

    def get_file_key(self, days):
        """
        days：查询多少天
        id：日期+查询天数合成的ID，防止执行重复任务
        """
        # 绘制并保存图表
        self.gen_graph(days)
        # 上传文件到服务器，回去回传的文件ID
        file_key = self.upload()
        return file_key