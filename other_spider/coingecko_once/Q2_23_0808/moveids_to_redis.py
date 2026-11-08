# def move_t():
#     path = 'other_spider/coingecko_once/Q2_23_0808/'
#
#     with open(f'{path}k.log') as f:
#         content = f.read().strip()
#     rows = content.split('\n')
#     from utils.redisdb import redis_cli
#     rc = redis_cli()
#     for row in rows:
#         item = row.strip().split('该日期无数据：')[-1]
#         rc.sadd('coingecko', item)
#         print(item)
#         # coins_list = json.loads(coins)