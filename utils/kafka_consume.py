import os
import json
import time

from kafka import KafkaConsumer


def kafkaconsum():
    channel = 'bilibili-20210321'
    kafka_topic = 'popinion-data-crawl-bilibili'
    # 线上环境
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '')
    kafka_args = {
        'group_id':f"{channel}",
        'auto_offset_reset':'earliest',
        # 'auto_offset_reset':'latest'

        # 'value_deserializer': lambda m: json.loads(m.decode('gbk')),
    }
    consumer = KafkaConsumer(kafka_topic, bootstrap_servers=bootstrap_servers, **kafka_args)
    while True:
        try:
            for msg in consumer:
                # value = msg.value.decode("utf-8")
                # recv = "%s:%d:%d: key=%s " % (msg.topic, msg.partition, msg.offset, msg.key)
                # print(recv)
                data = json.loads(msg.value.decode())
                source_channel_id = data['source_channel_id']
                spider_time = data['time']
                # ext_time = data['ext_fields']['data_time']
                if source_channel_id == 47:
                    if spider_time > 1618885930:
                        print(data)
                        # if data['time'] != ext_time:
                        #     data['time'] = ext_time
                        #     print(f'修复日期{data}')
            break
        except Exception as e:
            print(e)
            consumer.close()
            break


if __name__ == '__main__':
    kafkaconsum()