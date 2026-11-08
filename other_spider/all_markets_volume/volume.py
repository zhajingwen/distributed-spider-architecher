import time
import requests
import logging
import csv
from retry import retry
from utils.proxy_requests import proxies
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Volume MarketCapt Monitor')

class Spider:
    def __init__(self):
        self.jobs = {'AGB': 'apes-go-bananas', 'AIBB': 'bullbear-ai', 'AICODE': 'ai-code', 'AIDOGE': 'arbdoge-ai', 'ANALOS': 'analos', 'APX': 'apollox', 'ARBINU': 'arbinu', 'BABYBONK': 'baby-bonk-coin', 'BABYDRAGON': 'baby-dragon-coin', 'BABYELON': 'baby-elon', 'BABYGROK': 'baby-grok-bsc', 'BAD': 'bad-idea-ai', 'BEN': 'ben', 'BITCOIN': 'harrypotterobamasonic10inu-eth', 'BOME': 'book-of-meme', 'BONE': 'bone-shibaswap', 'BONK': 'bonk1', 'BRETT': 'based-brett', 'CAPO': 'il-capo-of-crypto', 'CHAD': 'chad-coin', 'CLIPS': 'clips-token', 'COQ': 'coq-inu', 'CULT': 'cult-dao', 'DINO': 'dinoswap', 'DOGE': 'dogecoin', 'DOGE2': 'dogecoin-2', 'DONS': 'the-dons', 'DORKL': 'dork-lord', 'DUKO': 'duko', 'ELON': 'dogelon', 'FINE': 'refinable', 'FLOKI': 'floki-inu', 'GROK': 'grok-erc', 'GUAC': 'guac', 'HAHA': 'hasaki', 'HAM': 'hamster', 'HIPP': 'el-hippo', 'HMTT': 'hype-meme-token', 'HOPPY': 'hoppy-token', 'INU': 'ryoshi-inu', 'KAKI': 'doge-kaki', 'LADYS': 'milady-meme-coin', 'LEASH': 'doge-killer', 'LOVELY': 'lovely-inu', 'LUFFY': 'luffy-v2', 'MEME': 'meme', 'MMIT': 'mangoman-intelligent', 'MMVG': 'memevengers', 'MOONEY': 'mooney', 'MYRO': 'myro', 'NEVER': 'neversol', 'OGGY': 'oggy-inu-eth', 'PAW': 'pawswap', 'PC': 'plug-chain', 'PEEPO': 'peepo', 'PENG': 'peng-sol', 'PEOPLE': 'constitutiondao', 'PEPE': 'pepe', 'PIT': 'pitbull', 'PLEB': 'plebtoken', 'PONKE': 'ponke', 'PORK': 'pepefork', 'RABBIT': 'richrabbit', 'REACH': 'reach', 'REKT': 'rekt-arb', 'RFD': 'refund', 'RIBBIT': 'ribbit-meme', 'SAMO': 'samoyedcoin', 'SEX': 'sex-one', 'SHEPE': 'shiba-v-pepe', 'SHIA': 'shiba-saga', 'SHIB': 'shiba-inu', 'SHIB2': 'shib2', 'SLERF': 'slerf', 'SMURFCAT': 'real-smurf-cat-eth', 'SNAP': 'snapex', 'SNEK': 'snek', 'SORA': 'sora-ai', 'SPONGE': 'sponge-token', 'STONKS': 'harrypotterobamawallstreetbets10inu', 'SUNDAE': 'sundaeswap', 'TAMA': 'tamadoge', 'TEST': 'test', 'THE': 'thena', 'TOKEN': 'tokenfi', 'TSUKA': 'dejitaru-tsuka', 'TURBO': 'turbo', 'UNLEASH': 'unleashclub', 'VINU': 'vita-inu', 'WEN': 'wen', 'WIF': 'dogwifhat', 'WOJAK': 'wojak', 'WOOF': 'woof', 'WOOO': 'wooonen', 'WSB': 'wall-street-bet', 'X': 'xerc20-pro', 'XEN': 'xen-crypto', 'YAMA': 'yama-inu', 'ZKPEPE': 'zkpepes'}
        # self.jobs = {'AGB': 'apes-go-bananas', 'AIBB': 'bullbear-ai', 'AICODE': 'ai-code', 'AIDOGE': 'arbdoge-ai', 'ANALOS': 'analos', 'APX': 'apollox', 'ARBINU': 'arbinu', 'BABYBONK': 'baby-bonk-coin', 'BABYDRAGON': 'baby-dragon-coin', 'BABYELON': 'baby-elon', 'BABYGROK': 'baby-grok-bsc', 'BAD': 'bad-idea-ai', 'BEN': 'ben', 'BITCOIN': 'harrypotterobamasonic10inu-eth', 'BOME': 'book-of-meme', 'BONE': 'bone-shibaswap', 'BONK': 'bonk1', 'BRETT': 'based-brett', 'CAPO': 'il-capo-of-crypto', 'CHAD': 'chad-coin', 'CLIPS': 'clips-token', 'COQ': 'coq-inu', 'CULT': 'cult-dao', 'DINO': 'dinoswap', 'DOGE': 'dogecoin', 'DOGE2': 'dogecoin-2', 'DONS': 'the-dons', 'DORKL': 'dork-lord', 'DUKO': 'duko', 'ELON': 'dogelon', 'FINE': 'refinable', 'FLOKI': 'floki-inu', 'GROK': 'grok-erc', 'GUAC': 'guac', 'HAHA': 'hasaki', 'HAM': 'hamster', 'HIPP': 'el-hippo', 'HMTT': 'hype-meme-token', 'HOPPY': 'hoppy-token', 'INU': 'ryoshi-inu', 'KAKI': 'doge-kaki', 'LADYS': 'milady-meme-coin', 'LEASH': 'doge-killer', 'LOVELY': 'lovely-inu', 'LUFFY': 'luffy-v2', 'MEME': 'meme', 'MMIT': 'mangoman-intelligent', 'MMVG': 'memevengers', 'MOONEY': 'mooney', 'MYRO': 'myro', 'NEVER': 'neversol', 'OGGY': 'oggy-inu-eth', 'PAW': 'pawswap', 'PC': 'plug-chain', 'PEEPO': 'peepo', 'PENG': 'peng-sol', 'PEOPLE': 'constitutiondao', 'PEPE': 'pepe', 'PIT': 'pitbull', 'PLEB': 'plebtoken', 'PONKE': 'ponke', 'PORK': 'pepefork', 'RABBIT': 'richrabbit', 'REACH': 'reach', 'REKT': 'rekt-arb', 'RFD': 'refund', 'RIBBIT': 'ribbit-meme', 'SAMO': 'samoyedcoin', 'SEX': 'sex-one', 'SHEPE': 'shiba-v-pepe', 'SHIA': 'shiba-saga', 'SHIB': 'shiba-inu', 'SHIB2': 'shib2', 'SLERF': 'slerf', 'SMURFCAT': 'real-smurf-cat-eth', 'SNAP': 'snapex', 'SNEK': 'snek', 'SORA': 'sora-ai', 'SPONGE': 'sponge-token', 'STONKS': 'harrypotterobamawallstreetbets10inu', 'SUNDAE': 'sundaeswap', 'TAMA': 'tamadoge', 'TEST': 'test', 'THE': 'thena', 'TOKEN': 'tokenfi', 'TSUKA': 'dejitaru-tsuka', 'TURBO': 'turbo', 'UNLEASH': 'unleashclub', 'VINU': 'vita-inu', 'WEN': 'wen', 'WIF': 'dogwifhat', 'WOJAK': 'wojak', 'WOOF': 'woof', 'WOOO': 'wooonen', 'WSB': 'wall-street-bet', 'X': 'xerc20-pro', 'XEN': 'xen-crypto', 'YAMA': 'yama-inu', 'ZKPEPE': 'zkpepes', 'GRIMACE': 'grimace-doge'}

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        file_name = 'result.csv'
        self.csvfile = open(file_name, 'a', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.csvfile)
        row = ['symbol', 'slug', '成交量', '占比', 'TOP1', '链接', '日期']
        self.writer.writerow(row)

    @retry(tries=6, delay=3)
    def volume(self, symbol, slug):
        """
        获取24小时交易量
        """
        url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/' \
              f'latest?slug={slug}&start=1&limit=100&category=spot&centerType=all' \
              '&sort=cmc_rank_advanced&direction=desc&spotUntracked=true'
        logger.info(f'GET: {url}')
        # res = requests.get(url, headers=self.headers, proxies=proxies)
        res = requests.get(url, headers=self.headers)
        logger.info(f'response: {res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'状态码异常 {res.status_code}')
        marketPairs = res.json()['data']['marketPairs']
        top_status = '否'
        volumeUsd = ''
        volumePercent = ''
        for index, marketPair in enumerate(marketPairs):
            exchangeSlug = marketPair['exchangeSlug']
            if exchangeSlug == 'mainex':
                if index == 0:
                    top_status = '是'
                volumeUsd = marketPair['volumeUsd']
                volumePercent = marketPair['volumePercent']
                volumePercent = round(volumePercent, 2)
                break
        cmc_url = f'https://coinmarketcap.com/currencies/{slug}/'
        current_date = datetime.now().strftime("%Y-%m-%d")
        row = [symbol, slug, volumeUsd, volumePercent, top_status, cmc_url, current_date]
        logger.info(row)
        self.writer.writerow(row)

    def get_volume(self):
        """
        获取所有代币市占率的情况
        """
        # 共120
        num = 0
        for symbol in self.jobs:
            slug = self.jobs[symbol]
            self.volume(symbol, slug)
            num += 1
            logger.info(f'已完成：{num}')
            time.sleep(10)
