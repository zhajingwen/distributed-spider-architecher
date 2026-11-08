# -*- coding: utf-8 -*-
import json
from base64 import b64decode
from datetime import datetime
from urllib.parse import parse_qsl
from scrapy_redis.spiders import RedisSpider

def gen_urls():
    base_url = 'https://dapps-rankings.dappradar.com/api/v1.0/rankings/dapps?params={}'
    params = [
        # all games
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1OaGRHVm5iM0o1U1dSYlhUMHhKbVpsWVhSMWNtVmtQVEU9',
        # all all
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1abFlYUjFjbVZrUFRFPQ==',
        # ethereum
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQweEptWmxZWFIxY21Wa1BURT0=',
        # binance-smart-chain
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQweE5TWm1aV0YwZFhKbFpEMHg=',
        # polygon
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQweE5pWm1aV0YwZFhKbFpEMHg=',
        # wax
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQweE1TWm1aV0YwZFhKbFpEMHg=',
        # solana
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQweU55Wm1aV0YwZFhKbFpEMHg=',
        # arbitrum
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQwMU5TWm1aV0YwZFhKbFpEMHg=',
        # optimism
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQwME5pWm1aV0YwZFhKbFpEMHg=',
        # base
        'UkdGd2NGSmhaR0Z5WTNWeWNtVnVZM2s5VlZORUpuTnZjblE5ZFdGM1EyOTFiblFtYjNKa1pYSTlaR1Z6WXlaeVlXNW5aVDB5TkdnbWNtVnpkV3gwYzFCbGNsQmhaMlU5TWpVbWNHRm5aVDB4Sm1Ob1lXbHVTV1JiWFQwNU5DWm1aV0YwZFhKbFpEMHg='
    ]
    urls = []
    for p in params:
        url = base_url.format(p)
        urls.append(url)
    return urls

class DappRadar(RedisSpider):
    name = 'dappradar'
    redis_key = f"{name}:start_url"
    change_ua = True
    # 每日早晨5：00调度
    cron_job = "0 5 * * *"
    start_urls = gen_urls()
    # 特殊pipeline
    custom_settings = {
        'ITEM_PIPELINES': {
            "scrapy_spider.ext_pipelines.rds_onchain_data_misc.MysqlPipeline": 100,
        }
    }

    def parse(self, response, **kwargs):
        """
        自定义开始请求
        """
        params = response.url.split('?params=')[-1]
        new_params = b64decode(b64decode(params)).decode('utf-8')
        params_dic = dict(parse_qsl(new_params))
        if 'chainId[]' in params_dic:
            chain = params_dic['chainId[]']
            if chain == '1':
                chain = 'ETH'
            elif chain == '15':
                chain = 'BSC'
            elif chain == '16':
                chain = 'Polygon'
            elif chain == '11':
                chain = 'WAX'
            elif chain == '27':
                chain = 'Solana'
            elif chain == '55':
                chain = 'Arbitrum'
            elif chain == '94':
                chain = 'Base'
            elif chain == '46':
                chain = 'Optimism'
        else:
            chain = 'all'
        self.logger.info(f'chain: {chain}')
        if 'categoryId[]' in params_dic:
            category = params_dic['categoryId[]']
            if category == '1':
                category = 'GameFi'
        else:
            category = 'all'
        results = json.loads(response.body)['results']
        categorys = {
            1: 'games',
            2: 'defi',
            3: 'collectibles',
            4: 'gambling',
            5: 'other',
            6: 'high risk',
            7: 'marketplaces',
            8: 'exchanges',
            9: 'social'
        }
        chains = {
            "1": "ethereum",
            "2": "eos",
            "3": "tron",
            "6": "ontology",
            "11": "wax",
            "13": "hive",
            "15": "bnb chain",
            "16": "polygon",
            "17": "flow",
            "18": "near",
            "19": "avalanche",
            "21": "tezos",
            "23": "loTeX",
            "25": "harmony",
            "27": "solana",
            "29": "klaytn",
            "37": "cronos",
            "38": "moonriver",
            "39": "moonbeam",
            "40": "fantom",
            "43": "celo",
            "46": "optimism",
            "50": "aurora",
            "55": "arbitrum",
            "57": "dfk chain",
            "59": "kcc",
            "70": "skale",
            "94": "base"
        }
        sqls = []
        for i, item in enumerate(results):
            # 第一个是广告
            if i == 0:
                continue
            name = item['name']
            categoryId = item['categoryId']
            protocols = []
            for chain_id in item['chainIds']:
                if str(chain_id) in chains:
                    protocols.append(chains[str(chain_id)])
                else:
                    self.logger.error(f'chainid: {chain_id} {name}')
                    # protocols.append(chain_id)
            data = {
                'select_chain': chain,
                'select_cate': category,
                'rank': f'{i}',
                'name': name,
                'category': categorys[categoryId],
                'uaw': item['statistic']['uawCount'],
                'uaw_change': item['statistic']['uawCountChange'],
                'date': datetime.now().strftime("%Y-%m-%d"),
                'protocols': str(protocols), #所有公链id的list
            }
            sql = f"INSERT INTO dappradar2 (select_chain, select_cate, rank, name," \
                  f" category, uaw, uaw_change, date, protocols) VALUES ({repr(chain)}," \
                  f"{repr(category)},{repr(i)},{repr(name)},{repr(categorys[categoryId])}," \
                  f"{repr(data['uaw'])},{repr(str(data['uaw_change'])+'%')},{repr(data['date'])},{repr(data['protocols'])});"
            # uuid = md5(sql.encode()).hexdigest()
            sqls.append(sql)
        result = {
            # 'id':'',
            'sql': sqls
        }
        yield result
