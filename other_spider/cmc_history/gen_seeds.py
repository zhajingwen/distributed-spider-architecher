import json
from utils.redisdb import redis_cli
content = """
Coinbase	Marinade	MNDE	MNDE/USD	2022-11-02	否	https://coinmarketcap.com/currencies/mnde/
Coinbase	Marinade Staked SOL	MSOL	MSOL/USD	2022-11-02	否	https://coinmarketcap.com/currencies/marinade/
"""

# AIOZ, CUDOS, METIS, MTD, ZED,VELO, POLYX, GARI
redis_c = redis_cli()
key = "cmc:history:jobs_backup"

def gen():
    """
    生成任务
    """
    for row in content.strip().split('\n'):
        row_list = row.split('\t')
        full_name = row_list[1]
        abbreviation = row_list[2]
        url = row_list[-1]
        slug = url.split('/')[-1]
        if not slug:
            slug = url.split('/')[-2]
        print(slug)
        job = {
            'full_name':full_name,
            'abbreviation':abbreviation,
            'slug': slug,
        }
        redis_c.hset(key,slug,json.dumps(job))



