import json
import requests
import time
import logging
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NO Listing In Mainex')

class Spider:
    def __init__(self):
        """
        初步的过滤条件全部都在请求中参数中过滤了
        """
        self.base_url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?start={}&limit=100' \
                        '&sortBy=market_cap&sortType=desc&convert=USD,BTC,ETH&cryptoType=all&tagType=all' \
                        '&audited=false&aux=ath,atl,high24h,low24h,num_market_pairs,cmc_rank,date_added,' \
                        'max_supply,circulating_supply,total_supply,volume_7d,volume_30d,' \
                        'self_reported_circulating_supply,self_reported_market_cap&volume24hRange=1000000~'
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,und;q=0.7",
            "cache-control": "no-cache",
            "dnt": "1",
            "origin": "https://coinmarketcap.com",
            "platform": "web",
            "referer": "https://coinmarketcap.com/",
            "sec-ch-ua": "\"Google Chrome\";v=\"107\", \"Chromium\";v=\"107\", \"Not=A?Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.pagenum = 1
        self.redis_cli = redis_cli()
        self.job_key = f'noexistinmainex:jobs'

    @retry(tries=3, delay=6)
    def req(self, num=1):
        """
        发起请求拿数据
        """
        url = self.base_url.format(num)
        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'Response {res.status_code}: {url}')
        self.parse_list(res)

    def parse_list(self, response):
        """
        解析数据
        读写数据库，计算涨幅
        调用报警模块
        """
        if response.status_code != 200:
            logger.info(f'列表页状态码异常：{response.status_code}')
            raise
        else:
            time_stamp = int(time.time())
            cryptoCurrencyList = response.json()['data']['cryptoCurrencyList']
            totalCount = response.json()['data']['totalCount']
            totalCount = int(totalCount)
            logger.info(f'一共{totalCount}个数据')
            for cryptoCurrency in cryptoCurrencyList:
                self.parse_item(cryptoCurrency)
            # 翻页
            self.pagenum += 100
            if self.pagenum < totalCount:
                logger.info(f'当前翻页的起始值 {self.pagenum}')
                self.req(self.pagenum)
            else:
                # 当前的请求翻页结束的时候初始化该值
                self.pagenum = 1
                logger.info('翻页结束，初始化翻页计数')

    @retry(tries=3, delay=6)
    def get_contracts_address(self, slug):
        """
        获取合约地址
        return: None or string
        """
        # 获取CMC能够查到的全部币种信息，通过此来做address匹配拿到slug
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'Response {res.status_code}: {url}')
        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        data = res.json()
        address = None
        matched = None
        for item in data['values']:
            if item[3] == slug:
                matched = True
                address = item[7]
                if address:
                    address = address[0]
        if not matched:
            logger.error(f'该币在CMC查询不到：{slug}')
            return
        # ["0.0.127877"] https://coinmarketcap.com/currencies/tune-fm/
        # 合约地址可能是个乱码，比如上面的例子
        if 40 <len(address)< 50:
            # https://coinmarketcap.com/currencies/krest-network/
            # 合约地址可能为空列表[],这种情况表示其是公链项目
            return address
        else:
            logger.info(f'slug: {slug} 在cmc清单匹配到的地址是假的：{address}')
            return

    def get_markets(self, slug):
        """
        过滤上线mainex的币种
        拿到没有上线mainex 币 的上线的交易所清单
        Return None or str
        """
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced'

        logger.info(f'Get: {url}')
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'Response {res.status_code}: {url}')
        data = res.json()

        data = data['data']
        marketPairs = data.get('marketPairs')
        if marketPairs:
            exchangeNames = []
            for i in marketPairs:
                exchangeName = i['exchangeName']
                # 防止重复
                if exchangeName not in exchangeNames:
                    exchangeNames.append(exchangeName)
            # 过滤已上线迪拜交易所的代币
            if 'Mainex' in exchangeNames:
                logger.info(f'已上线mainex：{slug}')
                return
            markets = ','.join(exchangeNames)
            return markets
        else:
            logger.info(f'查询到的交易所列表为空：{marketPairs}')
            return '未上线任何交易所'

    def parse_item(self, cryptoCurrency):
        """
        从每一个币中解析出详情
        """
        id = cryptoCurrency['id']
        name = cryptoCurrency['name']
        symbol = cryptoCurrency['symbol']

        quotes = cryptoCurrency['quotes']
        if quotes:
            detail = quotes[-1]
            percentChange1h = round(detail['percentChange1h'], 2)
            percentChange24h = round(detail['percentChange24h'], 2)
            price_usd = detail['price']
            volume24h = int(detail['volume24h'])
            marketCap = int(detail['marketCap'])
            slug = cryptoCurrency['slug']

            cmc_url = f'https://coinmarketcap.com/currencies/{slug}/'
            base_data = {
                'id': id,
                'name': name,
                'symbol': symbol,
                'percentChange1h': f"{percentChange1h}%",
                'percentChange24h': f"{percentChange24h}%",
                'price_usd': price_usd,
                'volume24h': volume24h,
                'marketCap': marketCap,
                'cmc_url': cmc_url,
                'slug': slug
            }
            address = self.get_contracts_address(slug)
            if address:
                base_data['address'] = address
            else:
                base_data['address'] = ''
                logger.error(f'无法解析出合约地址：{base_data}')
            # 当 markets 为None时需要过滤掉该数据
            markets = self.get_markets(slug)
            if not markets:
                return
            base_data['markets'] = markets
            job = json.dumps(base_data)
            # 将该基础数据作为任务塞入reids给dextools消费
            self.redis_cli.sadd(self.job_key, job)

    def run(self):
        self.req()
