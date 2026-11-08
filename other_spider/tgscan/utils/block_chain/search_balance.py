import logging
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
    logger.info(f"Wallet {wallet_address} balance: {balance_usdt} USDT")
    return balance_usdt

