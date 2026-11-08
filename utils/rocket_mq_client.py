# from mq_http_sdk.mq_exception import MQExceptionBase
# from mq_http_sdk.mq_consumer import *
# from mq_http_sdk.mq_client import *
#
# # 阿里巴巴rocketmq
# accessKeyId = '<ROCKETMQ_ACCESS_KEY_ID>'
# accessKey = '<ROCKETMQ_ACCESS_KEY_SECRET>'
# nameSrvAddr = 'http://<ROCKETMQ_INSTANCE_ID>.mqrest.<REGION>.aliyuncs.com'
# # nameSrvAddr = 'http://<ROCKETMQ_INSTANCE_ID>.mq-internet-access.mq-internet.aliyuncs.com:80 '
#
# # 初始化client。
# mq_client = MQClient(
#     # 设置HTTP协议客户端接入点，进入消息队列RocketMQ版控制台实例详情页面的接入点区域查看。
#     nameSrvAddr,
#     # AccessKey ID阿里云身份验证，在阿里云RAM控制台创建。
#     accessKeyId,
#     # AccessKey Secret阿里云身份验证，在阿里云RAM控制台创建。
#     accessKey
#      )
# # 消息所属的Topic，在消息队列RocketMQ版控制台创建。
# topic_name = 'amazon_item_dev'
# # 您在消息队列RocketMQ版控制台创建的Group ID。
# group_id = 'aoligei_goodsid'
#
# # Topic所属的实例ID，在消息队列RocketMQ版控制台创建。
# # 若实例有命名空间，则实例ID必须传入；若实例无命名空间，则实例ID传入空字符串。实例的命名空间可以在消息队列RocketMQ版控制台的实例详情页面查看。
# instance_id = '<ROCKETMQ_INSTANCE_ID>'
# # print(len(topic_name+group_id + instance_id))
#
# consumer = mq_client.get_consumer(instance_id, topic_name, group_id)
#
# # 长轮询表示如果Topic没有消息，则客户端请求会在服务端挂起3秒，3秒内如果有消息可以消费则立即返回响应。
# # 长轮询时间3秒（最多可设置为30秒）。
# wait_seconds = 3
# # 一次最多消费3条（最多可设置为16条）。
# batch = 3
# # print(("%sConsume And Ak Message From Topic%s\nTopicName:%s\nMQConsumer:%s\nWaitSeconds:%s\n" \
# #         % (10 * "=", 10 * "=", topic_name, group_id, wait_seconds)))
# while True:
#     # try:
#         # 长轮询消费消息。
#     recv_msgs = consumer.consume_message(batch, wait_seconds)
#     for msg in recv_msgs:
#             # print(("Receive, MessageId: %s\nMessageBodyMD5: %s \
#             #                   \nMessageTag: %s\nConsumedTimes: %s \
#             #                   \nPublishTime: %s\nBody: %s \
#             #                   \nNextConsumeTime: %s \
#             #                   \nReceiptHandle: %s \
#             #                   \nProperties: %s\n" % \
#             #       (msg.message_id, msg.message_body_md5,
#             #        msg.message_tag, msg.consumed_times,
#             #        msg.publish_time, msg.message_body,
#             #        msg.next_consume_time, msg.receipt_handle, msg.properties)))
#             # print(msg.get_property(""))
#             print(msg.message_body)
#     # except MQExceptionBase as e:
#     #     # Topic中没有消息可消费。
#     #     if e.type == "MessageNotExist":
#     #         print(("No new message! RequestId: %s" % e.req_id))
#     #         continue
#     #
#     #     print(("Consume Message Fail! Exception:%s\n" % e))
#     #     time.sleep(2)
#     #     continue
#
#     # msg.next_consume_time前若不确认消息消费成功，则消息会被重复消费。
#     # 消息句柄有时间戳，同一条消息每次消费拿到的都不一样。
#     try:
#         receipt_handle_list = [msg.receipt_handle for msg in recv_msgs]
#         consumer.ack_message(receipt_handle_list)
#         print(("Ak %s Message Succeed." % len(receipt_handle_list)))
#     except MQExceptionBase as e:
#         print(("\nAk Message Fail! Exception:%s" % e))
#     # time.sleep(3)