import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DATA Filter')

class Filter:
    def filter_list_data_early(self,data_list):
        """
        早期造富的过滤条件
        过滤列表页非目标数据
        测试发现该过滤条件过滤后只有第一页是有数据的，后面几乎会全部都被过滤掉
        """
        """
        {
			"tn": "pTokens GALA",       # 全称
			"vn": 2212827.2857963783,   # 成交量
			"nh": 2753,                 # 24小时新增持有人
			"txn": 20576,               # 交易笔数
			"sellnum": 310342872.1285771, # 未知
			"buynum": 309954003.6015801,  # 未知
			"up": 0.00235218183689193,    # 当前价
			"r5m": 0.06912122974875701,    # 涨幅
			"r1h": -0.09624154146073491,   # 涨幅
			"r4h": -0.5236120277091543,    # 涨幅
			"r24h": 1.2014878999473921,     # 涨幅 
			"pb": 11100.432435860259,   # 流动池
			"token": "0x7dDEE176F665cD201F93eEDE625770E2fD911990", 通用代币地址的概念
			"sy": "GALA",    # 简称
			"ps": "USDT",    # 计价单位
			"tbname": "d0xebdff5ca393cb96bfc06da51008b9c4265b4c36c" dexfilter内部ID
		}
        """
        new_list = []
        for data in data_list:
            # 可能为0 ZeroDivisionError: float division by zero
            if not data['pb']:
                logger.info(f'市值为0{data}')
                continue
            # 换手率 得大于50%
            turnover_rate = data['vn']/data['pb']
            if turnover_rate > 0.5:
                # 流动池大于20k USD
                if data['pb'] > 20000:
                    # 24小时交易量 大于等于 10K
                    if data['vn'] > 10000:
                        # 24小时交易笔数 大于等于 200
                        if data['txn'] > 200:
                            # 24小时新增持有人 大于等于200
                            if data['nh'] > 200:
                                # 打标成早期造富
                                data['nt'] = 1
                                data['turnover_rate'] = turnover_rate
                                new_list.append(data)
        return new_list

    def filter_list_data_marketcap(self,data_list):
        """
        小市值的过滤条件
        """
        new_list = []
        for data in data_list:
            # 流动池大于20k USD
            if data['pb'] > 20000:
                # 1小时交易笔数  大于等于60
                if data['txn'] > 60:
                    # 1小时交易量 大于等于10K USDT
                    if data['vn'] > 10000:
                        # 1小时涨幅 大于等于 0%，即上涨；
                        if data['r1h'] > 0:
                            # 打标成小市值
                            data['nt'] = 0
                            new_list.append(data)
        return new_list