# -*- coding: utf-8 -*-
import os
import json
import ccxt
from retry import retry
from scrapy.http import Request
from scrapy_redis.spiders import RedisSpider
from utils.proxy_requests import proxies
from utils.lark_bot import sender

class ScanCoins(RedisSpider):
    name = 'scan_high_exchange_rate'
    redis_key = f"{name}:start_url"
    change_ua = True
    list_url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?' \
               'start={}&limit=100&sortBy=market_cap&sortType=desc&convert=USD,BTC,ETH&' \
               'cryptoType=all&tagType=all&audited=false&aux=ath,atl,high24h,low24h,' \
               'num_market_pairs,cmc_rank,date_added,max_supply,circulating_supply,' \
               'total_supply,volume_7d,volume_30d,self_reported_circulating_supply,' \
               'self_reported_market_cap'
    url = list_url.format(1)
    start_urls = [url]
    # 每小时调度一次
    schedule_time = 12 * 60
    black_key_base = 'cmc:black:strong:'
    # 这些币不在统计范围
    names_black_list = [
        'TrueUSD', 'USDD', 'USDT', 'USD Coin', 'Fei USD', 'Venus USDT', 'Origin Dollar',
        'USDC', 'Tether', 'Ethereum', 'Ankr Staked ETH', 'Liquity USD', 'TNC Coin',
        'Dai', 'Gemini Dollar', 'sUSD', 'Pax Dollar', 'Dai', 'Venus USDC', 'USDJ', 'USDX [Kava]',
        'cVault.finance', 'Venus BUSD', 'Binance USD', 'Celo Dollar', 'USTC', 'PYUSD'
    ]
    # 将报警过的币，推送给热门板块程序做统计
    hot_category_jobs = "crypto_hot_category:start_url"
    web_hook_api = os.getenv('LARK_WEBHOOK_CMC_4', '')

    @retry(tries=10, delay=3)
    def ccxt_get(self):
        """
        获取BTC1小时单位的K线数据 1000小时
        """
        exchange = ccxt.binance({'proxies': proxies})
        ohlcv_btc = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=1000)
        return ohlcv_btc

    def parse(self, response, **kwargs):
        """
        解析详情页，提取category
        """
        self.logger.info(f'Parse {response.url}')
        try:
            data = json.loads(response.body)
            cryptoCurrencyList = data['data']['cryptoCurrencyList']
        except:
            self.logger.error(f'列表页解析失败：{response.body}')
            return
        # 翻页
        page_num = response.meta.get('page_num',0)
        # 每小时调度时刷新BTC数据
        if page_num == 0:
            self.ohlcv_btc = self.ccxt_get()
        next_page_num = page_num + 1
        if next_page_num < 2:
            now_start_num = 1 + 100 * next_page_num
            list_url = self.list_url.format(now_start_num)
            yield Request(
                url=list_url,
                meta={
                    'page_num': next_page_num
                },
                dont_filter=True,
                callback=self.parse
            )
        cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
        for cryptoCurrency in cryptoCurrencyList:
            id = cryptoCurrency['id']
            name = cryptoCurrency['name']
            symbol = cryptoCurrency['symbol']
            slug = cryptoCurrency['slug']
            quotes = cryptoCurrency['quotes']
            # 数据不完整
            if not quotes:
                self.logger.info(f'{symbol} 没有计价单位')
                return
            # 3小时内强势计数过的，过滤
            key = self.black_key_base + str(id)
            status = self.server.get(key)
            if status:
                self.logger.warning(f'{name} {status}')
                return
            # 自定义黑名单
            if name in self.names_black_list:
                return
            if symbol in self.names_black_list:
                return
            # BTC计价的 需要全部大于0
            price_basebtc = quotes[0]
            percentChange7d_basebtc = price_basebtc['percentChange7d']
            # 7天涨幅强于btc，那么才往下执行
            if percentChange7d_basebtc > 0:
                data = {
                    'id': id,
                    'name': name,
                    'symbol': symbol,
                    'slug': slug,
                    'url': f'https://coinmarketcap.com/currencies/{slug}/'
                }
                # 校验36h、3天、7天、14天
                url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart?id={id}&range=1M'
                yield Request(
                    url=url,
                    meta={
                        'data_res': data
                    },
                    callback=self.parse_one_month_data
                )

    def check_servral_days(self, coin_ohlcv, h):
        """
        时间区间h内涨幅是否同时大于BTC和ETH
        """
        ohlcv_btc = self.ohlcv_btc
        status = True
        # 目标币 h 小时内的涨幅
        start_target_coin = int(-1 - h/2)
        coin_amplitude = (coin_ohlcv[-1] - coin_ohlcv[start_target_coin])/coin_ohlcv[start_target_coin]
        # BTC h 小时内的涨幅
        start_btc = -1 - h
        btc_amplitude = (ohlcv_btc[-1][4]-ohlcv_btc[start_btc][4])/ohlcv_btc[start_btc][4]
        # 近H小时涨幅得大于BTC
        if coin_amplitude < btc_amplitude:
            status = False
        return status

    def push_job_to_hot_categroy(self, data):
        """
        将币推送给热门板块统计程序消费
        """
        slug = data['slug']
        url = f'https://coinmarketcap.com/currencies/{slug}/'
        job = {
            'url': url
        }
        # 将任务推送给"热门板块"程序消费
        self.server.lpush(self.hot_category_jobs, json.dumps(job))

    def alert(self, data):
        """
        结构化数据，调用报警模块
        """
        msg = f"""
        Token Name：{data['name']}

        Token Symbol：{data['symbol']}

        CMC链接：{data['url']}
        """
        id = data['id']
        # 如果存在，那么就不报警 由于高并发可能导致重复报警，redis去重失效的情况，需要进行二次验证
        key = self.black_key_base + str(id)
        status = self.server.get(key)
        if status:
            self.logger.warning(f'{data["name"]}存在于黑名单{status}')
            return
        symbol = data['symbol']
        # 强势持续时间指数
        incr_key = f'cmc:strong:coins:{symbol}'
        self.server.incr(incr_key)
        # 新增过期时间 防止key无限堆积
        self.server.expire(incr_key, 7 * 24 * 60 * 60)
        # 强势持续时间指数
        num = self.server.get(incr_key)
        num = int(num)
        msg += f'\n递增持续时间指数: {num}'
        sender(msg, self.web_hook_api, '强势币')
        # 设置过期时间3h内报过警的就不要报了
        value = '3小时内有过强势记录'
        self.server.set(key, value, ex=3 * 60 * 60)

    def parse_one_month_data(self, response):
        self.logger.info(f'Parse {response.url}')
        try:
            data = json.loads(response.body)
            points = data['data']['points']
        except:
            self.logger.error(f'列表页解析失败：{response.body}')
            return
        coin_ohlcv = []
        for time_s in points:
            price = points[time_s]['v'][0]
            coin_ohlcv.append(price)
        for h in [36,72,168,336]:
            status = self.check_servral_days(coin_ohlcv, h)
            # 但凡在1-14天内，有一个时间区间弱势，都跳出
            if not status:
                return
        data_res = response.meta['data_res']
        self.logger.info(f'告警：{data_res}')
        # 告警到lark
        self.alert(data_res)
        self.push_job_to_hot_categroy(data_res)
