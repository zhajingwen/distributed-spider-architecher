import logging
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TwitterScan Spider')


class Test:
    def __init__(self):
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9",
            "dnt": "1",
            "sec-ch-ua": "\"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"108\", \"Google Chrome\";v=\"108\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        self.rds = DataUtils('spider')
        self.table_trending = 'twitterscan_trendingtokens'
        self.table_kol = 'twitterscan_kol'
        self.super_kol_tokens = []
        self.super_kol_data = []
        self.builder_tokens = []
        self.builder_data = []
        self.vc_tokens = []
        self.vc_data = []


    def parse_trending(self):
        """
        解析trending tokens
        """
        yesterday = '2022-12-14'
        coin_name = 'USDT'
        select_sql = f'select scores from {self.table_trending} where ' \
                     f'coin_name={repr(coin_name)} and spider_date={repr(yesterday)};'
        old_scores = self.rds.select(select_sql)
        print(old_scores)
        if old_scores == ():
            print('ok')
        if old_scores:
            old_scores = old_scores[0]['scores']
            print(old_scores)