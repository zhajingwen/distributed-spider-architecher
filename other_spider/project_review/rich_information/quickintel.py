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

        # 是否放弃合约
        contract_Renounced = quickiAudit.get('contract_Renounced')
        false_list['contract_Renounced'] = contract_Renounced
        false_list['黑名单'] = quickiAudit.get('can_Blacklist')
        # false_list['can_Blacklist'] = quickiAudit.get('can_Blacklist')
        false_list['可销毁代币'] = quickiAudit.get('can_Burn')
        false_list['可增发'] = quickiAudit.get('can_Mint')
        false_list['批量黑名单'] = quickiAudit.get('can_MultiBlacklist')
        false_list['可暂停交易'] = quickiAudit.get('can_Pause_Trading')
        false_list['可修改税收'] = quickiAudit.get('can_Update_Fees')
        false_list['限制交易次数'] = quickiAudit.get('can_Update_Max_Tx')
        false_list['限制交易钱包数'] = quickiAudit.get('can_Update_Max_Wallet')
        false_list['可修改特定钱包交易费用'] = quickiAudit.get('can_Update_Wallets')
        false_list['白名单'] = quickiAudit.get('can_Whitelist')
        false_list['cant_Pause_Trading_Renounced'] = quickiAudit.get('cant_Pause_Trading_Renounced')
        false_list['存在外部合约风险'] = quickiAudit.get('has_External_Contract_Risk')
        false_list['has_External_Functions'] = quickiAudit.get('has_External_Functions')
        false_list['has_General_Vulnerabilities'] = quickiAudit.get('has_General_Vulnerabilities')
        false_list['由已知的诈骗钱包资助'] = quickiAudit.get('has_Known_Scam_Wallet_Funding')
        false_list['has_ModifiedTransfer_Warning'] = quickiAudit.get('has_ModifiedTransfer_Warning')
        false_list['has_Obfuscated_Address_Risk'] = quickiAudit.get('has_Obfuscated_Address_Risk')
        false_list['has_Scams'] = quickiAudit.get('has_Scams')
        false_list['包含可疑操作'] = quickiAudit.get('has_Suspicious_Functions')
        false_list['交易冷却'] = quickiAudit.get('has_Trading_Cooldown')
        false_list['隐藏所有者'] = quickiAudit.get('hidden_Owner')
        false_list['代理合约'] = quickiAudit.get('is_Proxy')
        false_list['貔貅'] = tokenDynamicDetails['is_Honeypot']
        for key in false_list:
            value = false_list[key]
            if value:
                if key == 'contract_Renounced':
                    key = '放弃合约'
                # risk_content += f'{key}: {value};  '
                risk_content += f'{key};  '
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

    def get_total_supply(self, data):
        """
        获取总供应量
        """
        tokenDetails = data['tokenDetails']
        tokenDecimals = tokenDetails['tokenDecimals']
        tokenSupply = tokenDetails['tokenSupply']
        # total_supply = tokenSupply*(10**tokenDecimals)
        return tokenSupply, tokenDecimals

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 万亿
        if num > 1000000000000:
            num = round((num / 1000000000000), 2)
            num = f'{num}T'
        # 10亿 转换成xxB
        elif num > 1000000000:
            num = round((num/1000000000),2)
            num = f'{num}B'
        else:
            # 100w  转换成xxM
            if num > 1000000:
                num = round((num/1000000), 2)
                num = f'{num}M'
            else:
                # 转换成xxK
                if num > 1000:
                    num = round((num / 1000), 2)
                    num = f'{num}K'
                else:
                    num = int(num)
        return num

    @retry(tries=6, delay=3)
    def top_holders(self, supply, tokenDecimals, address, chain):
        """
        获取前10持仓地址
        """
        data = {"jsonrpc": "2.0", "method": "nr_getTokenHolders",
                "params": [address, "0xA", "", "0xA"], "id": 1}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.quickintel.io/scanner'
        }
        url = f'https://{chain}-mainnet.nodereal.io/v1/f3b37cc49d3948f5827621b8c2e0bdb3'
        logger.info(f'POST: {url} {data}')
        res = requests.post(url, headers=headers, json=data, proxies=proxies, impersonate='chrome101')
        logger.info(f'Response {res.status_code}: {url}')
        details = res.json()['result']['details']
        holders_content_list = []
        head_content = '👇\n'
        for holder in details:
            accountAddress = holder['accountAddress']
            tokenBalance = holder['tokenBalance']
            tokenBalance = int(int(tokenBalance, 16)/(10**tokenDecimals))
            hold_percent = round((tokenBalance/supply)*100, 2)
            hold_content = f'<i>        {accountAddress}  {self.num_transform(tokenBalance)}  {hold_percent}%</i>'
            holders_content_list.append(hold_content)

        content = '\n'.join(holders_content_list)
        head_content += content
        return head_content

    def holders(self, data, address, chain):
        """
        持币地址数据
        """
        tokenDecimals = 0
        supply = None
        holders_content = None
        try:
            supply, tokenDecimals = self.get_total_supply(data)
        except:
            logger.error(format_exc())
        # 如果能够获取到总供应量
        if supply:
            try:
                holders_content = self.top_holders(supply, tokenDecimals, address, chain)
            except:
                logger.error(format_exc())
                holders_content = '持币地址获取异常，请联系管理员'
        return holders_content

    @retry(tries=6, delay=3)
    def transactions_info_get(self, chain, address):
        """
        请求合约检测 + 供应量数据 + 持币地址信息
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
            # return risk_result
        except:
            logger.error(format_exc())
            risk_result = 'quick合约检测异常，请联系管理员'
        if chain == 'solana':
            holders_content = 'solana'
        else:
            holders_content = self.holders(data, address, chain)
        return risk_result, holders_content

    def quickintel(self, data):
        """
        想合约检测结果组合到data中
        """
        chain = data['base_info']['公链']
        if chain == 'ether':
            chain = 'eth'
        if chain == 'solana':
            logger.info(f'solana链不用quickintel进行合约检测')
            return data
        if chain not in self.chains:
            chain_exsist_status = False
            for c in self.chains:
                if chain in c:
                    chain = c
                    chain_exsist_status = True
                    break
            if not chain_exsist_status:
                logger.error(f'无法匹配到公链：{chain} {data}')
                return data
        address = data['base_info']['代币地址']
        # 拿到合约检测结果
        combined_info_result = self.transactions_info_get(chain, address)
        risk_result, holders_content = combined_info_result
        if risk_result:
            data['chain_data']['合约风险quickintel'] = risk_result
        else:
            data['chain_data']['合约风险quickintel'] = '无'
            logger.info(f'无合约风险quickintel：{address} {chain}')
        # 持币地址可以通过多渠道获取，quickintel 不支持solana链，考虑从其他渠道获取
        if '持币地址' not in data['chain_data']:
            data['chain_data']['持币地址'] = holders_content
        data['link']['quickintel_url'] = f'https://app.quickintel.io/scanner?type=token&chain={chain}&contractAddress={address}'
        return data
