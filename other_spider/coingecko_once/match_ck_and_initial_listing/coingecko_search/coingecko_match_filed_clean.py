import logging
import json
from utils.redisdb import redis_cli

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Coingecko Search')

class Identify:
    def __init__(self, market):
        self.cant_matched_count = 0
        self.more_matched_count = 0
        self.redis_cli = redis_cli()
        self.symbols_key = f'coingecko_once:{market}:symbols'

    def identify_coingecko_match(self, name, coingecko_match):
        """
        name: str  原始数据中的name（代币全称）
        coingecko_match: list   search接口拿到的list
        cant_matched_count：int  无法匹配的数量
        cant_matched_count：int  过多匹配的数量
        清洗 coingecko_match
        当该字段： coingecko_match list中有多个值的时候，进行清洗处理，匹配到真正的目标字段
        return: None or dict
        """
        # 转成小写
        origin_name = name.strip().lower()
        origin_names = origin_name.split(' ')
        # 存储匹配结果list(dict)
        matched = []
        for item in coingecko_match:
            coingecko_matched_name = item['name'].lower()
            # 迭代原始的name，看在不在coingeck name 中
            for mn in origin_names:
                # 匹配上了
                if mn in coingecko_matched_name:
                    # 避免重复
                    if item not in matched:
                        # 加入匹配上的列表
                        matched.append(item)
        # 如果都没匹配上再和 cg ID匹配一次
        if not matched:
            for item in coingecko_match:
                id = item['id'].lower()
                # 迭代抹茶拿到的name，看在不在coingeck name 中
                for mn in origin_names:
                    # 匹配上了
                    if mn in id:
                        # 加入匹配上的列表
                        matched.append(item)
        # 异常情况 该情况可以敲定coingeck未收录
        if not matched:
            self.cant_matched_count += 1
            return None
        else:
            if len(matched) == 1:
                return matched[0]
            # 异常情况（多个匹配结果）
            else:
                # 全称匹配模式
                new_matched = []
                for item in matched:
                    coingecko_matched_name = item['name'].lower()
                    if origin_name == coingecko_matched_name:
                        if item not in new_matched:
                            # 加入匹配上的列表
                            new_matched.append(item)
                if len(new_matched) == 1:
                    return new_matched[0]
                else:
                    new_new_matched = []
                    # mexc name全程转换形态和 cg ID进行匹配
                    for item in matched:
                        id = item['id']
                        origin_name_formated = ''.join(origin_names)
                        if origin_name_formated == id:
                            if item not in new_new_matched:
                                # 加入匹配上的列表
                                new_new_matched.append(item)
                        else:
                            origin_name_formated = '-'.join(origin_names)
                            if origin_name_formated == id:
                                if item not in new_new_matched:
                                    # 加入匹配上的列表
                                    new_new_matched.append(item)
                    if len(new_new_matched) == 1:
                        return new_new_matched[0]
                    if len(new_new_matched) > 1:
                        self.more_matched_count += 1
                        logger.info(f'{self.more_matched_count} 全称&ID 多匹配 {origin_name}  {matched}')
                        return new_new_matched[0]
                    elif len(new_new_matched) == 0:
                        # 搜索结果无法匹配上
                        self.cant_matched_count += 1
                        return None

    def matched_data_clean(self):
        """
        对匹配到的原始数据进行清洗
        作用字段：coingecko_match
        字段类型 False or list
        list: 0 - N个元素
        将list变为 单个JSON或者 "-"
        """
        all_data = self.redis_cli.hgetall(self.symbols_key)
        self.cant_matched_count = 0
        self.more_matched_count = 0
        # 未收录统计
        no_employ_count = 0
        for symbol in all_data:
            orin_data = all_data[symbol]
            item = json.loads(orin_data)
            coingecko_match = item['coingecko_match']
            # 尚未被清洗的部分数据 （coingecko_match 字段）
            if isinstance(coingecko_match, list):
                if coingecko_match == []:
                    matched = '-'
                    no_employ_count += 1
                elif len(coingecko_match) == 1:
                    matched = coingecko_match[0]
                else:
                    # 原始 name
                    origin_name = item['name']
                    matched = self.identify_coingecko_match(origin_name, coingecko_match)
                    if not matched:
                        matched = '-'
                        no_employ_count += 1
                item['coingecko_match'] = matched
            data_update = json.dumps(item)
            self.redis_cli.hset(self.symbols_key, symbol, data_update)
        logger.info(f'coingecko_match 清洗完毕，未收录：{no_employ_count}')