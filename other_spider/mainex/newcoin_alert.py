from config.exchange import ccxt_exchange
import os
import logging
import time
import ccxt
import json
from traceback import format_exc
from datetime import datetime,timedelta
from utils.redisdb import redis_cli
from utils.lark_bot import sender
from hashlib import md5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NewCoin Alert')

class NewCoinAlert:
    def __init__(self):
        self.redis_cli = redis_cli()
        # set
        self.newcoin_alert_jobs = 'mainex:newcoin:alert:jobs'
        # set
        self.filter = 'mainex:newcoin:alert:filter'
        self.webhook_api = os.getenv('LARK_WEBHOOK_MAINEX', '')
        self.marketpercent_jobs = 'mainexmarketpercent:jobs'

    def coin_online_status(self, symbol, id):
        """
        1、过滤还没开放交易的：获取不到K线数据的过滤
        2、过滤不是最近5日开放交易的：不是最近5日上线的过滤
        """
        current_time = datetime.now()
        # 生成最近5日的日期列表（字符串形式）
        date_str_list = []
        for i in range(5):
            # N日前日期
            target_datetime = current_time - timedelta(days=i)
            target_ago_date = target_datetime.date()
            # 将N日前日期转换为字符串
            target_date_str = target_ago_date.strftime('%Y-%m-%d')
            date_str_list.append(target_date_str)
        try:
            exchange = ccxt_exchange()
            marketPair = f'{symbol}/USDT'
            ohlcv = exchange.fetch_ohlcv(marketPair, timeframe='1d', limit=10)
            if ohlcv:
                # 转换成秒
                the_first_day_timestamp = ohlcv[0][0]/1000
                # 第一根K线的所属日期
                first_trade_date = datetime.fromtimestamp(the_first_day_timestamp).strftime('%Y-%m-%d')
                if first_trade_date in date_str_list:
                    return first_trade_date
                else:
                    # 历史老币加入去重队列
                    self.redis_cli.sadd(self.filter, id)
                    logger.info(f'不在最近5日内上线：{symbol}')
            else:
                logger.info(f'尚未开放交易：{symbol}')
            return
        except:
            error_content = format_exc()
            if 'mainex does not have market symbol'in error_content:
                logger.info(f'该币等待上线中：{symbol}')
            else:
                logger.error(f'请求错误：{error_content}')
            return

    def deal_with(self, job):
        """
        是最近两日上线的，且没有推送过的，发送告警
        """
        name_symbol = job.split('/')
        name = name_symbol[0]
        symbol = name_symbol[1]
        logger.info(f'开始处理任务：name: {name} symbol: {symbol}')

        # 由于可能重名或重简称，需要根据下面的方式来生成去重ID
        new_filter_content = f'{name} (${symbol})'
        # 生成该币的唯一特征
        new_filter_id = md5(new_filter_content.encode()).hexdigest()

        # 判断该币是否需要过滤（已经告警过了 + 老币）
        filter_status = self.redis_cli.sismember(self.filter, new_filter_id)
        # 过滤
        if filter_status:
            logger.info(f'已告警：{new_filter_content}')
            return

        # 判断是否是最近两日上线的，存在则拿到上币日期，昨日或者今日
        alert_status = self.coin_online_status(symbol, new_filter_id)
        if alert_status:
            # 上币日期
            listing_trade_time = alert_status
            # 将任务塞入到 市占率监控的程序队列中
            self.redis_cli.hset(self.marketpercent_jobs, name, json.dumps({"symbol":symbol, "listing_date":listing_trade_time}))
            sender(new_filter_content, self.webhook_api, '新币')
            # 告警后，记录币的ID，为后面做去重
            self.redis_cli.sadd(self.filter, new_filter_id)

    def consumer(self):
        """
        从 other_spider/coingecko_once/mainex/names_symbols.py  接受任务，消费
        """
        content = 'other_spider/coingecko_once/mainex/names_symbols.py  接受任务，消费'
        logger.info(f'开始监听任务：{content}')
        while True:
            job = self.redis_cli.spop(self.newcoin_alert_jobs)
            if job:
                self.deal_with(job)
            else:
                # logger.info('没有任务')
                time.sleep(10)


