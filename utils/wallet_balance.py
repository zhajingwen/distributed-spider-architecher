import os
import logging
import asyncio
import time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Balance Search')

async def balance_search(wallet_address):
    """
    查询地址余额
    比如：wallet_address = '0xYourWalletAddress'
    交互频率限制：10K/5min. https://docs.bnbchain.org/docs/rpc
    """
    # https://bsc-dataseed3.binance.org/   https://bsc-dataseed.bnbchain.org  https://bsc-dataseed.binance.org/
    bsc_url = 'https://bsc-dataseed.bnbchain.org'
    web3 = Web3(Web3.HTTPProvider(bsc_url))
    web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    checksum_address = Web3.to_checksum_address(wallet_address)

    # USDT contract address on BSC
    usdt_contract_address = '0x55d398326f99059ff775485246999027b3197955'

    # ABI for the balanceOf function
    usdt_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"}]
    usdt_contract_address_checksum = Web3.to_checksum_address(usdt_contract_address)
    usdt_contract = web3.eth.contract(address=usdt_contract_address_checksum, abi=usdt_abi)

    # Get the balance of the wallet address
    balance = usdt_contract.functions.balanceOf(checksum_address).call()

    # Convert the balance from wei to USDT
    # <class 'decimal.Decimal'>
    balance_usdt = web3.from_wei(balance, 'ether')

    # Print the balance
    # logger.info(f"Wallet {wallet_address} balance: {balance_usdt} USDT")
    return balance_usdt

async def balance_search_bnb(wallet_address):
    """
    查询地址BNB余额
    比如：wallet_address = '0xYourWalletAddress'
    交互频率限制：10K/5min. https://docs.bnbchain.org/docs/rpc
    """
    # https://bsc-dataseed3.binance.org/   https://bsc-dataseed.bnbchain.org  https://bsc-dataseed.binance.org/
    bsc_url = 'https://bsc-dataseed.bnbchain.org'
    web3 = Web3(Web3.HTTPProvider(bsc_url))
    # 查询 BNB 余额（单位为 wei，需要转换为 BNB）
    balance_wei = web3.eth.get_balance(wallet_address)  # 获取余额（单位：wei）
    balance_bnb = web3.from_wei(balance_wei, "ether")  # 转换为 BNB 单位
    # print(f"钱包地址 {wallet_address} 的 BNB 余额为: {balance_bnb} BNB")
    return balance_bnb

async def check(wallet_address_list):
    for i in wallet_address_list:
        balance = await balance_search(i)
        if balance > 9:
            print(i, balance)

async def check_bnb(wallet_address_list):
    """
    钱包有USDT余额的地址，校验起bnb余额
    """
    for i in wallet_address_list:
        balance = await balance_search(i)
        if balance > 9:
            print(i, balance)

def send_usdt(address, sender_private_key, receiver_address, amount_usdt):
    """
    address: 发送方地址
    sender_private_key： 发送方私钥
    receiver_address：接收方地址
    amount_usdt：发送代币的数量
    """
    # 防止自己转给自己
    if address == receiver_address:
        return
    # 连接到币安智能链节点
    bsc_url = 'https://bsc-dataseed.binance.org/'
    web3 = Web3(Web3.HTTPProvider(bsc_url))

    # 检查连接是否成功
    if web3.is_connected():
        print("Connected to Binance Smart Chain")
    else:
        print("Failed to connect")

    sender_address = web3.to_checksum_address(address)

    # USDT代币合约地址（BEP20）
    usdt_contract_address = '0x55d398326f99059ff775485246999027b3197955'

    # 将地址转换为ChecksumAddress
    sender_address = web3.to_checksum_address(sender_address)
    receiver_address = web3.to_checksum_address(receiver_address)
    usdt_contract_address = web3.to_checksum_address(usdt_contract_address)

    # USDT代币合约ABI（简化版，包含transfer方法）
    usdt_abi = '''
    [
        {
            "constant": false,
            "inputs": [
                {
                    "name": "_to",
                    "type": "address"
                },
                {
                    "name": "_value",
                    "type": "uint256"
                }
            ],
            "name": "transfer",
            "outputs": [
                {
                    "name": "",
                    "type": "bool"
                }
            ],
            "type": "function"
        }
    ]
    '''

    # 初始化USDT合约
    usdt_contract = web3.eth.contract(address=usdt_contract_address, abi=usdt_abi)
    amount = int(amount_usdt * 10 ** 18)

    # 获取nonce值
    nonce = web3.eth.get_transaction_count(sender_address)

    # 获取当前推荐的Gas价格
    current_gas_price = web3.eth.gas_price
    # 将Gas价格转换为Gwei以便于阅读
    current_gas_price_gwei = web3.from_wei(current_gas_price, 'gwei')
    print(f'当前GASwei: {current_gas_price_gwei}')

    # 构建交易
    tx = usdt_contract.functions.transfer(receiver_address, amount).build_transaction({
        'chainId': 56,  # BSC主网的chainId
        'gas': 40000,  # USDT 正常在40000左右，建议设置上限为200000（确保能正常执行完，否则执行一半，消耗的手续费是不退的）
        'gasPrice': current_gas_price,
        'nonce': nonce,
    })

    # 签名交易
    signed_tx = web3.eth.account.sign_transaction(tx, sender_private_key)

    # 发送交易
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f'Transaction sent with hash: {tx_hash.hex()}')

    # 获取交易回执以查看实际使用的Gas量
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt['status'] == 0:
        print("Transaction failed")
    else:
        print(f'succeeded receipt: {receipt}')

def send_bnb(receiver_address, sender_address, sender_private_key):
    """
    发送BNB到目标地址
    """
    # 连接到币安智能链节点
    bsc_url = 'https://bsc-dataseed.binance.org/'
    web3 = Web3(Web3.HTTPProvider(bsc_url))

    # isConnected()
    # 检查连接是否成功
    if web3.is_connected():
        print("Connected to Binance Smart Chain")
    else:
        print("Failed to connect")


    sender_address = web3.to_checksum_address(sender_address)
    # 转账金额（BNB为单位，1 BNB = 10^18 wei）
    # 一笔USDT转账需要消耗GAS 0.00002- 0.00004， 故0.00007足够完成一笔USDT转账
    amount = web3.to_wei(0.00007, 'ether')

    # 假设当前价为 1
    # gasPrice = web3.to_wei(1, 'gwei')

    # 获取当前推荐的Gas价格
    current_gas_price = web3.eth.gas_price
    # 将Gas价格转换为Gwei以便于阅读
    current_gas_price_gwei = web3.from_wei(current_gas_price, 'gwei')
    print(f'当前GASwei: {current_gas_price_gwei}')
    # 构建交易
    # 获取nonce值
    nonce = web3.eth.get_transaction_count(sender_address)
    tx = {
        'nonce': nonce,
        'to': receiver_address,
        'value': amount,
        'gas': 21000,  # 简单转账的Gas限制
        'gasPrice': current_gas_price  # Gas价格
    }

    # 使用web3.py库签名交易
    signed_tx = web3.eth.account.sign_transaction(tx, sender_private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    # 获取交易哈希
    print(f'Transaction sent with hash: {tx_hash.hex()}')


async def transfer_usdt_to_main_wallet(wallet_address_list, address_private_key_map):
    """
    当钱包有USDT余额的地址时：
        校验bnb余额，当有BNB余额的时：
            将其USDT转出到主钱包
    """
    receiver_usdt_address = os.getenv('MAIN_WALLET_ADDRESS', '')
    for i in wallet_address_list:
        balance = await balance_search(i)
        if balance > 9:
            bnb = await balance_search_bnb(i)
            if bnb > 0:
                sender_private_key = address_private_key_map[i]
                amount_usdt = int(balance)
                if i != receiver_usdt_address:
                    print('开始转移到主钱包')
                    print(i, balance, bnb)
                    send_usdt(i, sender_private_key, receiver_usdt_address, amount_usdt)
            else:
                print(i, balance, bnb)
                print('bnb余额不足，不足以支付gas费')
                print('开始转移GAS费0.00007，从主钱包到目标钱包')
                send_bnb(i, receiver_usdt_address, address_private_key_map[receiver_usdt_address])
                print(f'{i} 接收GAS成功，等待到账中...')
                # 这里一个有一个判断GAS是否到账的操作
                time.sleep(2*60)
                # USDT归集
                sender_private_key = address_private_key_map[i]
                amount_usdt = int(balance)
                print(f'{i} USDT 开始归集到主钱包')
                send_usdt(i, sender_private_key, receiver_usdt_address, amount_usdt)
                print(f'{i} 归集成功')

if __name__ == '__main__':
    # asyncio.run(balance_search_bnb('0xYourWalletAddress'))
    addresses = ['0xYourWalletAddress']
    address_private_key_map = {}
    asyncio.run(transfer_usdt_to_main_wallet(addresses, address_private_key_map))
