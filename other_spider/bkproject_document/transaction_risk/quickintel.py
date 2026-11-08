from curl_cffi import requests
import json
import logging
from traceback import format_exc
from retry import retry
from utils.proxy_requests import proxies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Quickintel')

class Quickintel:

    def __init__(self):
        # post 接口
        self.api = 'https://app.quickintel.io/api/quicki/getquickiauditfull'
        # quickintel的所有公链
        self.chains = ['eth', 'arbitrum', 'bsc', 'core', 'kava', 'polygon', 'metis', 'astar', 'oasis', 'avalanche', 'fantom', 'zksync', 'polygonzkevm', 'loop', 'conflux', 'canto', 'iotex', 'energi', 'velas', 'grove', 'pulse', 'linea', 'base', 'maxx', 'besc', 'shibarium', 'opbnb', 'bitrock', 'scroll', 'lightlink', 'mantle', 'optimism', 'klaytn', 'solana', 'radix', 'injective', 'sui']

    def risk_check(self, data):
        """
        合约风险检测
        """
        quickiAudit = data['quickiAudit']
        tokenDynamicDetails = data['tokenDynamicDetails']
        false_list = {}
        risk_content = ''

        # 正常为True
        contractVerified = data['contractVerified']
        if not contractVerified:
            risk_content += f'contractVerified: 失败;  '

        # 正常为False
        false_list['can_Blacklist'] = quickiAudit.get('can_Blacklist')
        false_list['can_Burn'] = quickiAudit.get('can_Burn')
        false_list['can_Mint'] = quickiAudit.get('can_Mint')
        false_list['can_MultiBlacklist'] = quickiAudit.get('can_MultiBlacklist')
        false_list['can_Pause_Trading'] = quickiAudit.get('can_Pause_Trading')
        false_list['can_Update_Fees'] = quickiAudit.get('can_Update_Fees')
        false_list['can_Update_Max_Tx'] = quickiAudit.get('can_Update_Max_Tx')
        false_list['can_Update_Max_Wallet'] = quickiAudit.get('can_Update_Max_Wallet')
        false_list['can_Update_Wallets'] = quickiAudit.get('can_Update_Wallets')
        false_list['can_Whitelist'] = quickiAudit.get('can_Whitelist')
        false_list['cant_Pause_Trading_Renounced'] = quickiAudit.get('cant_Pause_Trading_Renounced')
        false_list['has_External_Contract_Risk'] = quickiAudit.get('has_External_Contract_Risk')
        false_list['has_External_Functions'] = quickiAudit.get('has_External_Functions')
        false_list['has_General_Vulnerabilities'] = quickiAudit.get('has_General_Vulnerabilities')
        false_list['has_Known_Scam_Wallet_Funding'] = quickiAudit.get('has_Known_Scam_Wallet_Funding')
        false_list['has_ModifiedTransfer_Warning'] = quickiAudit.get('has_ModifiedTransfer_Warning')
        false_list['has_Obfuscated_Address_Risk'] = quickiAudit.get('has_Obfuscated_Address_Risk')
        false_list['has_Scams'] = quickiAudit.get('has_Scams')
        false_list['has_Suspicious_Functions'] = quickiAudit.get('has_Suspicious_Functions')
        false_list['has_Trading_Cooldown'] = quickiAudit.get('has_Trading_Cooldown')
        false_list['hidden_Owner'] = quickiAudit.get('hidden_Owner')
        false_list['is_Proxy'] = quickiAudit.get('is_Proxy')
        false_list['is_Honeypot'] = tokenDynamicDetails['is_Honeypot']
        for key in false_list:
            value = false_list[key]
            if value:
                risk_content += f'{key}: {value};  '

        # 交易税率
        buy_Tax = tokenDynamicDetails.get('buy_Tax',0)
        if not buy_Tax:
            buy_Tax = 0
        buy_Tax = float(buy_Tax)
        if buy_Tax > 10:
            risk_content += f'buy_Tax: {buy_Tax}%;  '

        sell_Tax = tokenDynamicDetails.get('sell_Tax',0)
        if not sell_Tax:
            sell_Tax = 0
        sell_Tax = float(sell_Tax)
        if sell_Tax > 10:
            risk_content += f'sell_Tax: {sell_Tax}%;  '

        transfer_Tax = tokenDynamicDetails.get('transfer_Tax',0)
        if not transfer_Tax:
            transfer_Tax = 0
        transfer_Tax = float(transfer_Tax)
        if transfer_Tax > 10:
            risk_content += f'transfer_Tax: {transfer_Tax}%;  '

        if risk_content:
            return risk_content
        else:
            return

    @retry(tries=6, delay=3)
    def transactions_info_get(self, chain, address):
        """
        请求合约检测
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.quickintel.io/scanner'
        }
        data = {
            'chain': chain,
            'tier': 'basic',
            'tokenAddress': address
        }
        logger.info(f'Post: {self.api} {data}')
        res = requests.post(self.api, data=json.dumps(data), headers=headers, proxies=proxies, impersonate='chrome101')
        logger.info(f'response: {res.status_code} {self.api}')

        if res.status_code != 200:
            raise Exception(f'响应码错误：{res.status_code}')
        data = res.json()
        try:
            # 合约风险检测结果
            risk_result = self.risk_check(data)
            return risk_result
        except:
            logger.error(format_exc())
            logger.error(f'无法被解析的data: {data}')
            return

    def quickintel(self, address, chain):
        """
        想合约检测结果组合到data中
        """
        if chain == 'ether':
            chain = 'eth'
        if chain not in self.chains:
            chain_exsist_status = False
            for c in self.chains:
                if chain in c:
                    chain = c
                    chain_exsist_status = True
                    break
            if not chain_exsist_status:
                logger.error(f'无法匹配到公链：{chain}')
                return
        risk_result = self.transactions_info_get(chain, address)
        return risk_result