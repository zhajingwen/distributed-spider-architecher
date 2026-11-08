import requests
import logging
from retry import retry
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Project Review CMC Spider')

class Cmc:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_cli = redis_cli()
        self.dextools_jobs = 'project_review_en_version:dextools:jobs'

    @retry(tries=5, delay=3)
    def req(self, url):
        res = requests.get(url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res.json()

    def calculate_total_markets_volume_24h(self, marketPairs):
        """
        获取整个市场的24H交易量（包括cex和dex）
        """
        volumeUsd = marketPairs[0]["volumeUsd"]
        volumePercent = marketPairs[0]["volumePercent"]/100
        if volumePercent and volumeUsd:
            total_volume = int(volumeUsd / volumePercent)
            return total_volume
        else:
            return 0

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
            num = round((num/1000000000),2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num/1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    def cex_req(self, slug, dextools_data):
        """
        请求CEX清单接口，获取CEX清单和24小时volume
        return: dict combined data
        """
        # 查询交易所（cex）列表接口
        url = f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=10&category=spot&centerType=cex&sort=cmc_rank_advanced'
        data = self.req(url)
        data = data['data']
        marketPairs = data.get('marketPairs')
        if marketPairs:
            total_24h_volume = self.calculate_total_markets_volume_24h(marketPairs)
            logger.info(f'已上线cex交易所：{marketPairs}')
            exchangeNames = []
            # 所有cex的交易量
            volume24h_cex = 0
            every_market_volume = '👇\n'
            for i in marketPairs:
                exchangeName = i['exchangeName']
                # 防止重复
                if exchangeName not in exchangeNames:
                    exchangeNames.append(exchangeName)
                volumePercent = i['volumePercent']
                volumePercent = round(volumePercent, 2)
                volumeUsd = i['volumeUsd']
                # 计算所有cex的交易量
                volume24h_cex += volumeUsd
                volumeUsd = self.num_transform(volumeUsd)
                every_market_volume += f'<i>        {exchangeName}: {(volumeUsd)}  {volumePercent}%</i>\n'
            dextools_data['chain_data']['已上线cex'] = exchangeNames
            dextools_data['chain_data']['各交易所交易量'] = every_market_volume.strip()
            dextools_data['chain_data']['24h全网交易量'] = self.num_transform(total_24h_volume)
            dextools_data['chain_data']['24h cex交易量'] = self.num_transform(volume24h_cex)
        else:
            logger.info(f'查询到的交易所列表为空：{marketPairs}')
        return dextools_data

    def get_cex_info(self, data_dextools):
        """
        通过cmc查询是否上线了中心化交易所
        return: dict combined data
        """
        # data为dextools采集到的字典信息
        address = data_dextools['base_info']['代币地址']
        # 获取CMC能够查到的全部币种信息，通过此来做address匹配拿到slug
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        data = self.req(url)
        slug = None
        for item in data['values']:
            if len(item) >= 7:
                # list
                cmc_addresses = item[7]
                # cmc 地址大小写标准很混乱，下面是为了做各种兼容
                if address in cmc_addresses:
                    slug = item[3]
                else:
                    if address.lower() in cmc_addresses:
                        slug = item[3]
                    else:
                        if cmc_addresses:
                            # 可能在列表中第二个元素且大小写不一致
                            for a in cmc_addresses:
                                a = a.lower()
                                if address.lower() == a:
                                    slug = item[3]
        if not slug:
            logger.error(f'该币在CMC查询不到：{address}')
            return
        data_dextools['link']['cmc'] = f'https://coinmarketcap.com/currencies/{slug}/'
        return self.cex_req(slug, data_dextools)

    def inherit_dextools(self, data):
        """
        获取CEX上线情况
        被dextools爬虫调度，合并两块的信息
        return: dict combined data
        """
        combined_data = self.get_cex_info(data)
        return combined_data

    def get_contracts_address(self, slug):
        """
        获取合约地址
        return: None or string
        """
        # 获取CMC能够查到的全部币种信息，通过此来做address匹配拿到slug
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        data = self.req(url)
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

    def run(self, url):
        """
        解析URL，并且采集数据
        样例URL：https://coinmarketcap.com/currencies/zilliqa/
        # https://coinmarketcap.com/dexscan/ethereum/0x1a4ba32a27ca192aa56b5cdf1fbf5a8ca9e2255e/
        该爬虫并不直接处理任务，而是生成任务塞入redis提交给dextools爬虫处理
        """
        # https://coinmarketcap.com/currencies/zilliqa/
        if 'currencies' in url:
            address = url.strip().split('currencies/')[-1]
            slug = address.split('/')[0]
            if '?' in slug:
                slug = slug.split('?')[0]
            # 合约地址
            contracts_address = self.get_contracts_address(slug)
        # https://coinmarketcap.com/dexscan/ethereum/0x1a4ba32a27ca192aa56b5cdf1fbf5a8ca9e2255e/
        else:
            contracts_address = None
            parts = url.split('/')
            for i in parts:
                if len(i) == 42:
                    contracts_address = i
            if not contracts_address:
                logger.error(f'输入的地址有误：{url}')
                return
        if contracts_address:
            # 其他字段通过redis队列提交任务交给dextools处理
            self.redis_cli.sadd(self.dextools_jobs,contracts_address)
            return True
        else:
            return False