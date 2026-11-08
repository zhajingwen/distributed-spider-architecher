import requests
import logging
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Gopluslabs')

class GoplusRisk:
    def __init__(self):
        # goplus公链ID映射
        # 有可能存在任务包中的公链不在下面的dict中
        self.chains ={
            "ethereum": "1",
            "optimism": "10",
            "cronos": "25",
            "bsc": "56",
            "okc": "66",
            "gnosis": "100",
            "heco": "128",
            "polygon": "137",
            "fantom": "250",
            "kcc": "321",
            "zksync": "324",
            "ethw": "10001",
            "fon": "201022",
            "arbitrum": "42161",
            "avalanche": "43114",
            "linea": "59140",
            "harmony": "1666600000",
            "tron": "tron",
            "ether": "1",
        }
        self.base_url = 'https://api.gopluslabs.io/api/v1/token_security/{}?contract_addresses={}'
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }

    @retry(tries=5, delay=3)
    def req(self, url):
        """
        发起合约检测请求
        """
        res = requests.get(url, headers=self.headers, proxies=proxies)
        logger.info(f'{res.status_code} {url}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        return res

    def risk(self, goplus):
        """
        输出代币风险
        return: str 合约风险信息
        """
        all_status = []
        is_mintable = goplus.get('is_mintable', 0)
        cannot_buy = goplus.get('cannot_buy', 0)
        cannot_sell_all = goplus.get('cannot_sell_all', 0)
        honeypot_with_same_creator = goplus.get('honeypot_with_same_creator', 0)
        is_in_dex = goplus.get('is_in_dex', 0)
        is_open_source = goplus.get('is_open_source', 0)
        is_proxy = goplus.get('is_proxy', 0)
        anti_whale_modifiable = goplus.get('anti_whale_modifiable', 0)
        can_take_back_ownership = goplus.get('can_take_back_ownership', 0)
        external_call = goplus.get('external_call', 0)
        hidden_owner = goplus.get('hidden_owner', 0)
        is_blacklisted = goplus.get('is_blacklisted', 0)
        is_honeypot = goplus.get('is_honeypot', 0)
        # is_mintable = goplus.get('is_mintable', 0)
        is_whitelisted = goplus.get('is_whitelisted', 0)
        owner_balance = goplus.get('owner_balance', 0)
        owner_change_balance = goplus.get('owner_change_balance', 0)
        personal_slippage_modifiable = goplus.get('personal_slippage_modifiable', 0)
        selfdestruct = goplus.get('selfdestruct', 0)
        slippage_modifiable = goplus.get('slippage_modifiable', 0)
        trading_cooldown = goplus.get('trading_cooldown', 0)
        transfer_pausable = goplus.get('transfer_pausable', 0)


        if int(is_mintable) == 1:
            is_mintable = '可增发'
            all_status.append(is_mintable)
        if int(cannot_buy) == 1:
            cannot_buy = '不可买入'
            all_status.append(cannot_buy)
        if int(cannot_sell_all) == 1:
            cannot_sell_all = '不可全部卖出'
            all_status.append(cannot_sell_all)
        if int(is_open_source) == 0:
            is_open_source = '没开源'
            all_status.append(is_open_source)
        if int(is_proxy) == 1:
            is_proxy = '有代理合约'
            all_status.append(is_proxy)
        if int(anti_whale_modifiable) == 1:
            anti_whale_modifiable = '反巨鲸可修改'
            all_status.append(anti_whale_modifiable)
        if int(can_take_back_ownership) == 1:
            can_take_back_ownership = '能取回所有权'
            all_status.append(can_take_back_ownership)
        if int(external_call) == 1:
            external_call = '存在外部调用'
            all_status.append(external_call)
        if int(hidden_owner) == 1:
            hidden_owner = '存在隐藏owner'
            all_status.append(hidden_owner)
        if int(is_blacklisted) == 1:
            is_blacklisted = '存在黑名单机制'
            all_status.append(is_blacklisted)
        if int(is_honeypot) == 1:
            is_honeypot = '貔貅盘'
            all_status.append(is_honeypot)
        if int(is_whitelisted) == 1:
            is_whitelisted = '存在白名单机制'
            all_status.append(is_whitelisted)
        if int(owner_change_balance) == 1:
            owner_change_balance = 'owner可修改余额'
            all_status.append(owner_change_balance)
        if int(personal_slippage_modifiable) == 1:
            personal_slippage_modifiable = '滑点可修改'
            all_status.append(personal_slippage_modifiable)
        if int(selfdestruct) == 1:
            selfdestruct = '可自毁'
            all_status.append(selfdestruct)
        if int(slippage_modifiable) == 1:
            slippage_modifiable = '滑点可修改'
            all_status.append(slippage_modifiable)
        if int(trading_cooldown) == 1:
            trading_cooldown = '交易可冷却'
            all_status.append(trading_cooldown)
        if int(transfer_pausable) == 1:
            transfer_pausable = '交易可暂停'
            all_status.append(transfer_pausable)
        if not all_status:
            return ''
        content = ','.join(all_status)
        return content

    def check_risk(self, addresss, chain_name):
        """
        goplus的一些过滤规则（在dexcreener过滤之后进行）
        return：None or another_user_a_project_job  None就跳出
        """
        if chain_name not in self.chains:
            return
        # 合约检测
        chain_id = self.chains[chain_name]
        url = self.base_url.format(chain_id, addresss)
        res = self.req(url)
        if not res:
            logger.error(f'请求失败：{url}')
            return
        data = res.json()['result']
        if not data:
            logger.error(f'无数据：{url}')
            return
        data = data[addresss.lower()]
        risk_content = self.risk(data)
        return risk_content
