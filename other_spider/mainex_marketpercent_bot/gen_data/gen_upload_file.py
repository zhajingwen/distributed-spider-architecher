import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from utils.redisdb import redis_cli
from utils.rds import DataUtils
from utils.lark_bot_response import Send
import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from other_spider.mainex_marketpercent_bot.config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gen Graph')

class GenFileId:
    def __init__(self, id):
        self.job_id = id
        self.redis_cli = redis_cli()
        self.table_name = 'mainex_marketpercent'
        self.rds = DataUtils()
        self.send = Send(app_id, app_secret, app_name)
        self.file_name_rank = f'{id}rank.png'
        self.file_name_percent = f'{id}percent.png'
        self.redis_jobkey = 'marketsharebot:coinsadjust:{}'

    def get_history_share(self, cmd):
        """
        从数据库读取历史gas数据
        """
        keyword, days = cmd
        if days <= 1:
            logger.warning('用户输入的天数小于2天，无法生成图表')
            return
        start_date = (datetime.now() - timedelta(days=days - 1))
        # 获取查询起点时间0点的时间戳
        timestamp = int(start_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        for key in [f'name="{keyword}"', f'symbol="{keyword}"', f'name="{keyword.lower()}"', f'symbol="{keyword.lower()}"']:
            sql = f'select `rank`,`volumePercent` from {self.table_name} where spider_time >= {timestamp} and {key};'
            logger.info(sql)
            data = self.rds.select(sql)
            if data:
                break
        if not data:
            logger.info(f'查询不到该币的数据：{cmd}')
            return
        rank_list = []
        volumePercent_list = []
        if data:
            for item in data:
                rank = item['rank']
                volumePercent = item['volumePercent']
                rank_list.append(rank)
                volumePercent_list.append(volumePercent)
        return rank_list, volumePercent_list

    def gen_graph_one(self, value_list, graph_type):
        """
        生成一张图表
        """
        if graph_type == 'rank':
            file_name = self.file_name_rank
        else:
            file_name = self.file_name_percent
        x = []
        y = []
        logger.info(f'y轴数据{value_list}')
        for index, value in enumerate(value_list):
            x.append(index + 1)
            y.append(value)
        # 计算变化百分比
        percentage_change = [None]  # 第一个点的变化百分比设为None
        for i in range(1, len(y)):
            # change = ((y[i] - y[i - 1]) / y[i - 1]) * 100
            # percentage_change.append(change)
            if y[i - 1] != 0:
                change = ((y[i] - y[i - 1]) / y[i - 1]) * 100
            else:
                change = None  # 或者使用一个标志值表示无法计算变化百分比
            percentage_change.append(change)

        # 生成折线图
        plt.plot(x, y)
        plt.title(f'{graph_type.upper()} Recent {len(value_list)} days')
        plt.xlabel('day')

        # 设置颜色和字体
        label_color = 'blue'  # 选择一个颜色
        label_font = {'family': 'serif', 'color': 'darkred', 'weight': 'normal', 'size': 13}  # 设置字体的样式
        # plt.ylabel('rank', color=label_color, fontdict=label_font)
        plt.ylabel(graph_type, color=label_color, fontdict=label_font)

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
        plt.savefig(file_name)
        plt.close()

    def gen_graph(self, cmd):
        """
        同时生成市占率图和市占率排名图
        """
        # 拿到历史数据
        history_data = self.get_history_share(cmd)
        if history_data:
            rank_list, volumePercent_list = history_data
            # 根据历史数据生成图表
            self.gen_graph_one(rank_list, 'rank')
            self.gen_graph_one(volumePercent_list, 'percent')
            return True
        return

    def upload(self, filename):
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
        file = open(filename, "rb")
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
        return image_key

    def get_file_key(self, cmd):
        """
        days：查询多少天
        id：日期+查询天数合成的ID，防止执行重复任务
        """
        # 绘制并保存图表
        result = self.gen_graph(cmd)
        # 当确实生成图表的时候再上传
        if result:
            files = [self.file_name_rank, self.file_name_percent]
            file_keys = []
            for filename in files:
                # 上传文件到服务器，回去回传的文件ID
                file_key = self.upload(filename)
                file_keys.append(file_key)
            # 将image_key存入redis, 当任务相同的时候，后面就不用重复生成image_key 了
            redis_key = self.redis_jobkey.format(self.job_id)
            image_key = ','.join(file_keys)
            # image_key有效期最长24小时，故设置过期时间
            self.redis_cli.setex(redis_key, 24 * 60 * 60, image_key)
            return file_keys
        return
