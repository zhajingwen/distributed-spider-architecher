from datetime import datetime


def gen_msg(json_data):
    """"


        - 时间：2022.11.18 16:00 UTC+8
    - Token Name：CentroFi
    - Token Symbol：CENTRO
    - 推荐理由：较火的早期项目
      - 流动池大小：38.6K；
      - 成交量：19.3K；
      - 换手率：50%；
      - 交易笔数：2523
      - 24小时新增持币地址数：232
      - 是否有合约漏洞：否
      - Dexfilter 链接：
              {
			"tn": "pTokens GALA",       # 全称
			"vn": 2212827.2857963783,   # 成交量
			"nh": 2753,                 # 24小时新增持有人
			"txn": 20576,               # 交易笔数
			"sellnum": 310342872.1285771, # 未知
			"buynum": 309954003.6015801,  # 未知
			"up": 0.00235218183689193,    # 未知
			"r5m": 0.06912122974875701,    # 涨幅
			"r1h": -0.09624154146073491,   # 涨幅
			"r4h": -0.5236120277091543,    # 涨幅
			"r24h": 1.2014878999473921,     # 涨幅
			"pb": 11100.432435860259,   # 流动池
			"token": "0x7dDEE176F665cD201F93eEDE625770E2fD911990",
			"sy": "GALA",    # 简称
			"ps": "USDT",    # 计价单位
			"tbname": "d0xebdff5ca393cb96bfc06da51008b9c4265b4c36c"
		}

cmc
{"tn": "TwitFi Token", "vn": 490765.3470497581, "nh": 204, "txn": 2475, "sellnum": 1721435.0904789213, "buynum": 2382159.4969905224, "up": 0.13208792027805072, "r5m": 0.010864123347176343, "r1h": 0.03541193565074863, "r4h": 0.01083208973431223, "r24h": 0, "pb": 229554.32720893805, "token": "0xd4Df22556e07148e591B4c7b4f555a17188CF5cF", "sy": "TWT", "ps": "WETH", "tbname": "d0x5c24b84701916d968dcc7bdd6a4c5236bed460b9", "nt": 1, "chain": "eth"}
 “交易热度高的小盘股” -> "小市值高热度项目", "较火的早期项目" -> "早期造富项目"
    """
    spider_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if json_data['nt'] == 1:
        reason = '早期造富项目'
        next_content = f"""24h成交量：{int(json_data['vn'])}$
        
        换手率：{round(json_data['turnover_rate']*100,2)}%
        
        24h交易笔数：{json_data['txn']}
    
        24小时新增持币地址数：{json_data['nh']}
        """
    else:
        reason = '小市值高热度项目'
        next_content = f"""独立持币地址数：{json_data['holders']}

        1小时交易笔数：{json_data['txn']}

        1小时交易量：{int(json_data['vn'])}$

        1小时涨幅：{round(json_data['r1h']*100,2)}%
        """

    msg = f"""
    时间：{spider_date}
    
    Token Name：{json_data['tn']}
    
    Token Symbol：{json_data['sy']}
    
    推荐理由：{reason}
    
    总市值：{json_data['total_value']}$
    
    流动池大小：{int(json_data['pb'])*2}$
    
    {next_content}
    是否有合约漏洞：否
    
    Dexfilter 链接：https://dexfilter.com/analysis/{json_data['chain'].upper()}/{json_data['id']}
    """
    return msg