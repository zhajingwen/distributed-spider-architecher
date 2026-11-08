import requests
import os
import logging
from retry import retry
from utils.proxy_requests import proxies
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Filter Job And Map It To CMC')
env = os.environ.get('env')

class FilterMap:
    def __init__(self):
        self.headers = {
            "referer": "https://coinmarketcap.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        self.redis_jobs = 'mainexmarketpercent:jobs'

    @retry(tries=5, delay=3)
    def req(self, url):
        if env == 'local':
            res = requests.get(url, headers=self.headers)
        else:
            res = requests.get(url, headers=self.headers, proxies=proxies)
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res.json()

    def get_cmc_allcoins(self):
        # 获取CMC能够查到的全部币种信息，通过此来做address匹配拿到slug
        url = 'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json'
        data = self.req(url)
        return data

    def get_slug(self, all_coins, keywords):
        """
        和CMC进行匹配
        """
        origin_name = keywords[0]
        origin_symbol = keywords[1]

        slug = None
        matched = None
        # name 与 name 匹配
        for item in all_coins['values']:
            name = item[1]
            if name == origin_name:
                matched = True
                slug = item[3]
                break
        if matched:
            return slug
        else:
            # oldname 与 symbol匹配
            for item in all_coins['values']:
                symbol = item[2]
                if symbol == origin_name:
                    matched = True
                    slug = item[3]
                    break
            if matched:
                return slug
            else:
                for item in all_coins['values']:
                    symbol = item[2]
                    if symbol == origin_symbol:
                        matched = True
                        slug = item[3]
                        break
                if matched:
                    return slug
                else:
                    logger.info(f'无法和CMC完成匹配：{keywords}')
                    return

    def repeat_names_list(self, redis_c):
        """
        return need to filter names
        """
        names = []
        redis_jobs = redis_c.hgetall(self.redis_jobs)
        if redis_jobs:
            for job_key in redis_jobs:
                names.append(job_key)
        return names

    def gen_jobs_items(self, redis_c, repeat_names):
        """
        generate target jobs list
        filter jobs  and return them
        """
        id_names_key = 'mainex:idsnames'
        symbol_ids = 'mainex:symbolids'
        id_name_map_data = redis_c.hgetall(id_names_key)
        symbol_id_map_data = redis_c.hgetall(symbol_ids)
        jobs = []
        total_coins_num = 0
        for symbol in symbol_id_map_data:
            total_coins_num += 1
            id = symbol_id_map_data[symbol]
            # 确保ID在 id_name_map_data 中
            if id in id_name_map_data:
                name = id_name_map_data[id]
                if name in repeat_names:
                    continue
                job = {"name": name, "symbol": symbol}
                jobs.append(job)
        logger.info(f'共 {total_coins_num} 币， 去重后产生 {len(jobs)} 个任务')
        return jobs

    def map_job_tocmc(self):
        """
        generate the jobs have been filtered
        return mapped to cmc jobs
        """
        redis_c = redis_cli()
        repeat_names = self.repeat_names_list(redis_c)
        # all jobs from listing in bitgejt
        jobs = self.gen_jobs_items(redis_c, repeat_names)
        logger.info('任务去重完成')
        # request all cmc coins list
        all_coins = self.get_cmc_allcoins()
        logger.info('CMC所有收录代币清单获取完成')
        new_jobs = []
        # map coinsadjust to cmc
        for job in jobs:
            symbol = job['symbol']
            keywords = [job['name'], symbol]
            # mapping to coinmarketcap
            slug = self.get_slug(all_coins, keywords)
            if not slug:
                continue
            job['slug'] = slug
            new_jobs.append(job)
        logger.info('Mainex上线币种与CMC数据匹配完成')
        # mapped to cmc jobs
        return new_jobs



