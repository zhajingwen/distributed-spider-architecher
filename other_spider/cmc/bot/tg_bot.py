import os
import requests
import logging
import time
from traceback import format_exc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TG BOT')

class TGbot:
    def send_full(self, json_data):
        num = 0
        while True:
            try:
                self.sender(json_data)
                break
            except:
                num +=1
                if num > 3:
                    logger.warning('重试超过次数...')
                    break
                logger.error('发送异常')
                logger.info(format_exc())
                logger.error('重试...')
                time.sleep(10)

    def sender(self, json_data, url=None, msg=None, data=None):
        """
        # 文本格式化官方文档
        https://open.larksuite.com/document/ukTMukTMukTM/uMDMxEjLzATMx4yMwETM?lang=zh-CN
        :param url: webhook地址
        :param msg: 需要发送的消息
        :return:
        """
        if not url:
            # 默认报警链接，也支持传参
            url = "https://api.telegram.org/bot" + os.getenv('TG_BOT_TOKEN_CMC', '') + "/sendMessage"
        if not msg:
            msg = f"""Mainex Coin Monitor Bot Report
                
                ⏰ Time：{json_data['spider_date']}  UTC/GMT+08:00
                🪙 Token Name：{json_data['name']}
                🪙 Token Symbol：{json_data['symbol']}
                📈15min Pump：{json_data['price_increase_format']}
                📈 1h Pump：{json_data['percentChange1h']}
                💰 Token Price：${json_data['price_usd']}
                📊 24h Volume Increase：{json_data['vol_diff_format']}
                📊 24h Volume：{json_data['vol_24h']}
                
                👉 CMC link：{json_data['cmc_url']}
                
                """ + (os.getenv('TG_PROMO_TEXT', ''))
        # remove the identation
        new_msg = []
        for row in msg.strip().split('\n'):
            if row:
                if row.strip():
                    row = row.strip()
            new_msg.append(row)
        new_msg = "\n".join(new_msg)
        if not data:
            data = {
                "chat_id": os.getenv("TG_CHAT_ID_CMC", ""),
                "parse_mode": "Markdown",
                "text": new_msg,
                # "message_thread_id": 2618,
                # "message_thread_id": 913,
                # "message_thread_id": 511,
                # "message_thread_id": 82616,
                'disable_web_page_preview':True

            }
        else:
            data['text'] = new_msg
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        # for message_thread_id in [1,511]:
        #     data['message_thread_id'] = message_thread_id
        #     res = requests.request("POST", url, headers=headers, data=data)
        #     logger.info(f'push to tg {res.text}')
        # data['message_thread_id'] = message_thread_id
        # 发送给两个频道
        logger.info(f'alertdata: {data}')
        res = requests.request("POST", url, headers=headers, data=data)
        logger.info(f'push to tg {res.text}')
        # data.pop('message_thread_id')
        # res = requests.request("POST", url, headers=headers, data=data)
        # logger.info(f'push to tg {res.text}')


