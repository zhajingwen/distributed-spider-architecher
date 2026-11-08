# -*- coding: utf-8 -*-
from kafka import KafkaProducer
from config import config
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Kafka Pipeline Monitor')


class KafkaPipeline:

    def __init__(self):

        self.producer = self.kafka_producer()

    def process_item(self, item, topic):
        """
        :key
        pop_id(渠道id_数据来源唯一id)
        md5(content md5)
        time(时间戳，整型)
        """
        if item == None and "html_source" in item:
            return
        self.producer.send(topic, value=item)
        self.producer.flush()
        logger.info(f'插入成功 {item}')

    # 获取生产者client
    def kafka_producer(self):
        bootstrap_servers = config.KAFKA_BOOTSTRAP_SERVERS
        kafka_args = config.KAFKA_ITEM_PRODUCER_PARAMS
        return KafkaProducer(bootstrap_servers=bootstrap_servers, **kafka_args)

    # 发送到kafka中
    def _process_item(self, item):
        topic = 'popinion-data-crawl-bh3-oppo-item'
        self.producer.send(topic, value=item)
        self.producer.flush()
        return item

