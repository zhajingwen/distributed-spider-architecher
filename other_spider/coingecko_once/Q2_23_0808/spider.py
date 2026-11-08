import json
import logging
import time
import datetime
import hashlib
import requests
from functools import wraps
from traceback import format_exc
from threading import Thread
from copy import deepcopy
from utils.rds import DataUtils
from utils.redisdb import redis_cli
from utils.proxy_requests import proxies
from .url_symbols import url_symbol
from .check import check



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko')

class Spider:

    def __init__(self):
        path = 'other_spider/coingecko_once/Q2_23_0808/'
        self.id_urls = {

        }
        with open(f'{path}jobs')as f:
            content = f.read().strip().split('\n')
            for row in content:
                url = row.strip()
                if url:
                    id = url.split('https://www.coingecko.com/en/coins/')[-1]
                    if '/' in id:
                        id = id.split('/')[0]
                    self.id_urls[id] = url
        self.rds = DataUtils('spider')
        self.redis_cli = redis_cli()
        self.duplitude_key = 'coingecko'

        # allkeys = self.redis_cli.keys()
        # print(allkeys)
        # if self.duplitude_key in allkeys:
        #     self.redis_cli.delete(self.duplitude_key)
        # result = self.redis_cli.smembers(self.duplitude_key)
        # print(result)

        self.ids_json = check()

    def retry(*args):
        """
        重试装饰器
        支持指定重试次数
        """
        logger.info(args)
        if args:
            num = args[0]
        else:
            num = 10
        def recive_func(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                """
                这里返回被装饰的函数的执行结果
                """
                retry_num = 0
                # success = False
                res = None
                while True:
                    try:
                        res = func(*args, **kwargs)
                        # success = True
                        break
                    except:
                        logger.warning(f'{func.__name__}网络请求失败，重试...')
                        error = format_exc()
                        if 'ProxyError' in error:
                            logger.warning(f'{func.__name__} ProxyErr')
                        elif '451 Client Error:' in error:
                            logger.warning(f'{func.__name__} 451 Client Err')
                        elif 'timed out' in error:
                            logger.warning(f'{func.__name__} time out')
                        elif 'SSLEOFError' in error:
                            logger.warning(f'{func.__name__} SSLEOFErr')
                        else:
                            logger.warning(f'{func.__name__} {error}')
                        retry_num += 1
                        if retry_num > num:
                            logger.warning(f'重试超过次数{args} {kwargs}')
                            break
                        # 重试依旧是等待3s，否则会把账号打废掉
                        time.sleep(3)
                return res
            return wrapper
        return recive_func

    @retry(3)
    def get_one_day(self, param, id, datadate, datatimestamp):
        """
        请求数据
        """
        # 请求去重
        content = f'{id}{param}'
        res_md5 = hashlib.md5(content.encode('utf8')).hexdigest()
        status = self.redis_cli.sismember(self.duplitude_key,res_md5)
        if status:
            logger.info(f'已采集 去重！：{content}')
            return
        headers = {
            "accept": "application/json"
        }
        # url = "https://api.coingecko.com/api/v3/coins/velo/history"
        url = f"https://api.coingecko.com/api/v3/coins/{id}/history"
        params = {
            # "05-04-2023"
            "date": param
        }
        response = requests.get(url, headers=headers, params=params,proxies=proxies)
        # response = requests.get(url, headers=headers, params=params)
        logger.info(f'{id} {param} {response.status_code}')
        try:
            volume = response.json()['market_data']['total_volume']['usd']
        except:
            if 'symbol' in response.json():
                self.redis_cli.sadd(self.duplitude_key, res_md5)
                logger.info(f'该日期无数据：{content}')
                self.redis_cli.sadd(self.duplitude_key, res_md5)
            else:
                logger.error(f"未知错误：{response.json()} {id}")
            return
        volume = int(volume)
        spider_time = int(time.time())
        url = self.id_urls[id]
        symbol = url_symbol[url]
        sql = f"replace into coingecko2 values ({repr(res_md5)},{repr(id)},{repr(symbol)}," \
              f"{volume},{repr(datadate)},{datatimestamp},{spider_time},{repr(url)});"
        self.rds.insert(sql)
        self.redis_cli.sadd(self.duplitude_key,res_md5)
        logger.info(f'成功入库：{content}')

    def one_date(self, param, datadate, datatimestamp):
        """
        所有日期，所有币种
        10并发/s  且每天的数据所有币种跑完再跑第二天的
        """
        ts = []
        # ids = ['fore-protocol', 'pepe-2-0', 'snkrz-fit', 'hamsters']
        new_id_urls = deepcopy(self.id_urls)
        # 无法匹配的ID
        ids_error = ['fortune-token', 'joseon-mun', 'stella', 'combo', 'global-digital-cluster-coin', 'function-x', 'work-quest', 'layerai', 'bware', 'global-fan-token#markets', 'tenet', 'constellation', 'the-dons', 'maro', 'shrooms', 'cyberstella-stella', 'ben', 'sponge', 'funtoken', 'soonverse', 'aicoin', 'map-protocol', 'open-campus', 'koyo-token', 'euro-tether', 'navcoin', 'doubledice', 'rekt-arb', 'voltage-finance', 'alex-lab', 'so-col', 'metfi', 'angelblock', 'panther-protocol']
        # 60月30日前无数据
        nodata_before0630 = ['aree-shards', 'joystream', 'grimace', 'blast-frontiers', 'magic-shiba-starter', 'love-earn-enjoy', 'sonic-inu', 'yuri', 'sell-token']
        # 已采集
        done = ['style-protocol', 'athos-finance', 'topdown-survival-shooter', 'xrp-classic-new', 'chain-guardians', 'fourcoin', 'axelar', 'suiswap', 'caw-ceo', 'pulsechain', 'degenreborn', 'freicoin', 'naetion', 'walken', 'chaingpt', 'galeon', 'suzuverse', 'sui', 'kcal', 'helium', 'taboo-token', 'gemhub', 'web3camp', 'hello-labs', 'meta-fps', 'litlab-games', 'playzap', 'wifi', 'aienglish', 'hepton', 'otterhome', 'arbipad', 'wefi-finance', 'tominet', 'zkdoge', 'arix', 'i-love-snoopy', 'veno-finance', 'floki', 'hibakc', 'favor', 'the-unfettered-souls', 'mooi-network', 'dons', 'tangible', 'maxity', 'aishiba', 'muratiai', 'snek', 'baby-doge-coin', 'acorn-protocol', 'sakai-vault', 'connectome', 'clips', 'monkeys-token', 'the-qwan', 'bobo-coin', 'zizy', 'antspace', 'space-id', 'treecle', 'mongcoin', 'mr-potato', 'ls-coin', 'teddy-doge', 'astra-dao', 'bware-infra', 'airtor-protocol', 'mythos', 'bistroo', 'rektskulls', 'flappymoonbird', 'apes-go-bananas', 'spgbb', 'wrapped-ordichains', 'me-gusta', 'cetus-protocol', 'klima-dao', 'cogito-protocol', 'omax-token', 'tomtomcoin', 'alaska-gold-rush', 'floki-ceo', 'aptopad', 'finblox', 'turbo', 'blocksquare', 'mass-vehicle-ledger', 'osmosis', 'adreward', 'zkapes-token', 'esco-coin', 'metavault-dao', 'shaun-inu', 'leandro-lopes', 'rubic', 'selfcrypto', 'tamadoge', 'blockchaingames', 'ilcapo', 'aped', 'ribbit-meme', 'orbofi-ai', 'stepn', 'galaxia', 'pay-coin', 'renq-finance', 'liquid-staking-derivative', 'biso', 'areon-network', 'profit-blue', 'vaiot', 'safe-anwang', 'access-protocol', 'karate-combat', 'milady-meme-coin', 'majo', 'lord-of-dragons', 'trillioner', 'agility', 'smardex', 'doge-blue', 'pomerium', 'bsv', 'true-usd', 'papi', 'six-network', 'magic-oi-money', 'stp-network', 'sui-launch-token', 'gains-network', 'iskra-token', 'haha', 'yesports', 'spider-man', 'chad-coin', 'pepegpt', 'metatime-coin', 'portuma', 'cheelee', 'weway', 'wojak', 'unleashclub', 'veritise', 'the-nemesis', 'giant-mammoth', 'delysium', 'vinlink', 'suia', 'myria', 'alchemy-pay', 'scooby-doo', 'fomo-eth', 'cryptopirates', 'kepple', 'pogai', 'gleec-coin', 'stader', 'gpt-guru', 'bhnetwork', 'sell-token', 'pepera', 'bitmex-token', 'bart-simpson-coin', 'calorie', 'custodiy', 'gnome', 'fairerc20', 'float-protocol', 'tcg-verse#markets', 'xodex', 'waifuai', 'hypercycle', 'sonic-inu', 'games-for-a-living', 'rangers-fan-token', 'kripto', 'blueart', 'doge-ceo', 'echelon-prime', 'kekya', 'metabeat', 'ordinals', 'liquity', 'derp-coin', 'turbos-finance', 'unidef', 'fluus', 'stonksdao', 'pip', 'algebra', 'alexgo', 'dimo', 'gode-chain', 'memeverse', 'zknftex', 'tenet-1b000f7b-59cb-4e06-89ce-d62b32d362b9', 'top-network', 'pizabrc', 'lbvivi', 'catgirl', 'nals', 'tether-eurt', 'shib-original-vision', 'multichain', 'ben-2', 'velodrome-finance', 'bob-token', 'greg', 'leox', 'project-xeno', 'the-virtua-kolect', 'shibarium-perpetuals', 'pomerium-ecosystem', 'ubxs-token', 'bananatok', 'ppizza', 'planet-token', 'perion', 'camelot-token', 'brn-metaverse', 'edfi', 'mememe', 'gelato', 'ordinex', 'shido', 'storepay', 'pepeai', 'kabosu-arbitrum', 'flexmeme', 'drac-ordinals', 'suipad', 'qitmeer-network', 'pink-bnb', 'spheresxs', 'pepe-coin-bsc', 'ai-network', 'yachtingverse', 'zzz', 'wiki-cat', 'abyss-world', 'iron-fish', 'pleb-token', 'reign-of-terror', 'x7-coin', 'wall-street-baby', 'verse-bitcoin', 'stella-fantasy-token', 'peepo', 'rugame', 'mongol-nft', 'tether-gold', 'ai-code', 'roseon', 'bitcoinpepe', 'izumi-finance', '3d3d', 'tezos-pepe', 'fasttoken', 'dynex', 'wewe', 'dextf', 'tabtrader', 'bear-inu', 'nordek', 'platform-of-meme-coins', 'financie-token', 'pooh', 'uniwhale', 'pepe', 'vela-token', 'blockchain-bets', 'pmg-coin', 'playa3ull-games', 'arbswap', 'palmswap', 'urdex-finance', 'sharbi', 'sponge-f08b2fe4-9d9c-47c3-b5a0-84c2ac3bbbff', 'velo', 'bluesale', 'project-galaxy', 'limewire-token', 'ethlas', 'marvellex-classic', 'zenpandacoin', 'renewable-energy', 'dinolfg', 'zoid-pay', 'oggy-inu', 'mfet', 'pendle', 'mangoman-intelligent', 'homer', 'edu-coin', 'octo-gaming', 'hold-vip', 'astrafer', 'noot', 'spheroid-universe', 'reality-metaverse', 'omega-network', 'maverick-protocol', 'nothing-token', 'hypergpt', 'noot-ordinals', 'quantum-resistant-ledger', 'sperax', 'refund', 'metfi', 'golcoin', 'coinzix-token', 'xcad-network-play', 'dream-machine-token', 'pepa-inu', 'pando', 'octavus-prime', 'ignore-fud', 'arbdoge-ai', 'ronin', 'degis', 'vmpx', 'disney', 'qlindo', 'dione', 'ultron', 'triall', 'white-whale', 'kaspa', 'canto', 'wistaverse', 'vow', 'propchain', 'affyn', '3-kingdoms-multiverse', 'centcex', 'eldarune', 'pepexl', 'love-hate-inu', 'relation-native-token', 'crown-token-77469f91-69f6-44dd-b356-152e2c39c0cc', 'l', 'bullbear-ai', 'kek', 'troll-face', 'xana', 'king', 'solana-inu', 'milk-alliance', 'soulsaver']
        for id in new_id_urls:
            # if id in ids_error:
            #     continue
            # if id in nodata_before0630:
            #     continue
            # if id in done:
            #     continue
            if id not in self.ids_json:
                continue
            new_id = self.ids_json[id]
            self.id_urls[new_id] = self.id_urls[id]
            # self.get_one_day(param, id, name, symbol, marketpair, datadate, datatimestamp)
            t = Thread(target=self.get_one_day,args=(param, new_id, datadate, datatimestamp,))
            t.start()
            ts.append(t)
            # time.sleep(0.02)
        # 限制N(币的数量)并发
        for t in ts:
            t.join()

    def run(self):
        """
        入口
        """
        # while True:
        today_now = datetime.datetime.now()
        start = today_now.replace(month=4,day=1)
        end = today_now.replace(month=6,day=30)
        while True:
            start_date = start.strftime('%Y-%m-%d %H:%M:%S')
            param = start.strftime('%d-%m-%Y')
            datatimestamp = int(start.timestamp())
            # 执行
            self.one_date(param,start_date,datatimestamp)
            start += datetime.timedelta(days=1)
            if start > end:
                break

