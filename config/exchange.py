"""
目标交易所相关配置，全部从环境变量读取，代码中不写死具体交易所。
"""
import os
import json

# ccxt 中的交易所 id
EXCHANGE_CCXT_ID = os.getenv('EXCHANGE_CCXT_ID', '')
# 交易所站点根地址，如 https://www.example.com
EXCHANGE_WEB_BASE = os.getenv('EXCHANGE_WEB_BASE', '')
# 现货交易页面模板，{} 处填交易对（如 BTCUSDT）
EXCHANGE_SPOT_PAGE_TPL = os.getenv('EXCHANGE_SPOT_PAGE_TPL', '')
# 现货行情列表页面（playwright 打开后抓包）
EXCHANGE_MARKETS_PAGE_URL = os.getenv('EXCHANGE_MARKETS_PAGE_URL', '')
# 创新区交易对列表接口
EXCHANGE_SYMBOL_PARTITION_URL = os.getenv('EXCHANGE_SYMBOL_PARTITION_URL', '')
# 币种链信息接口（playwright 抓包匹配的 url 片段）
EXCHANGE_COIN_CHAIN_URL_KEYWORD = os.getenv('EXCHANGE_COIN_CHAIN_URL_KEYWORD', '')
# K 线接口
EXCHANGE_CANDLES_API_URL = os.getenv('EXCHANGE_CANDLES_API_URL', '')
# 交易对 symbol 后缀（部分交易所接口需要）
EXCHANGE_SYMBOL_SUFFIX = os.getenv('EXCHANGE_SYMBOL_SUFFIX', '')


def spot_page_url(pair):
    return EXCHANGE_SPOT_PAGE_TPL.format(pair)


def ccxt_exchange(params=None):
    import ccxt
    if not EXCHANGE_CCXT_ID:
        raise RuntimeError('环境变量 EXCHANGE_CCXT_ID 未配置')
    return getattr(ccxt, EXCHANGE_CCXT_ID)(params or {})


def json_env(name, default=None):
    raw = os.getenv(name, '')
    if not raw:
        return default if default is not None else {}
    return json.loads(raw)
