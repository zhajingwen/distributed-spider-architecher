import openpyxl
"""
将数据从excel中抽取，并且转化为方便处理的JSON格式
"""
def format_json(categories):
    new_categories = {}
    for c in categories:
        c_list = categories[c]
        for item in c_list:
            item['category'] = [c]
            name = item['name']
            if name == '-':
                name = item['symbol']
            if name not in new_categories:
                new_categories[name] = item
            else:
                # old_item = new_categories[name]['category'].append(c)
                new_categories[name]['category'].append(c)
                # old_item['category'].append(c)
                # old_category_list = old_item['category']
                # old_category_list.append(c)
                # old_item['category'] = old_category_list
                # print(old_item)
                # print(new_categories)

                # print(f'重名: {item}')
            # new_categories.append(item)
    # print(new_categories)
    return new_categories

def format_origin_data():
    """
    将Excel的数据格式化为JSON
    {'BTC扩容': [{'name': 'Stacks', 'symbol': 'STX'}, {'name': 'RSK Infrastructure Framework', 'symbol': 'RIF'}, {'name': 'Bitcoin SV', 'symbol': 'BSV'}, {'name': 'Bitcoin Cash', 'symbol': 'BCH'}], '铭文': [{'name': '-', 'symbol': 'ORDI'}, {'name': '-', 'symbol': 'SATS'}, {'name': '-', 'symbol': 'RATS'}, {'name': '-', 'symbol': 'MUBI'}], 'Solana': [{'name': 'Solana', 'symbol': 'SOL'}, {'name': 'Jito', 'symbol': 'JTO'}, {'name': 'Raydium', 'symbol': 'RAY'}, {'name': 'Pyth Network', 'symbol': 'PYTH'}, {'name': 'Bonk', 'symbol': 'BONK'}, {'name': 'Jupiter', 'symbol': 'JUP'}, {'name': 'dogwifhat', 'symbol': 'WIF'}], 'Arbitrum': [{'name': 'Arbitrum', 'symbol': 'ARB'}, {'name': 'Magic', 'symbol': 'MAGIC'}, {'name': 'GMX', 'symbol': 'GMX'}, {'name': 'Xai', 'symbol': 'XAI'}, {'name': 'Radiant Capital', 'symbol': 'RDNT'}, {'name': 'Vela Token', 'symbol': 'VELA'}], 'Optimism': [{'name': 'Optimism', 'symbol': 'OP'}, {'name': 'Perpetual Protocol', 'symbol': 'PERP'}, {'name': 'Synthetix Network', 'symbol': 'SNX'}, {'name': 'Stargate Finance', 'symbol': 'STG'}, {'name': 'Sonne Finance', 'symbol': 'SONNE'}, {'name': 'Velodrome Finance', 'symbol': 'VELO'}], 'DEX': [{'name': 'Uniswap', 'symbol': 'UNI'}, {'name': 'Curve DAO', 'symbol': 'CRV'}, {'name': '1inch', 'symbol': '1INCH'}, {'name': 'Sushi', 'symbol': 'SUSHI'}, {'name': 'Balancer', 'symbol': 'BAL'}, {'name': 'Pancake Swap', 'symbol': 'CAKE'}], 'Lending': [{'name': 'MakerDAO', 'symbol': 'MKR'}, {'name': 'AAVE', 'symbol': 'AAVE'}, {'name': 'Compound', 'symbol': 'COMP'}, {'name': 'Radiant Capital', 'symbol': 'RDNT'}], 'Derivatives': [{'name': 'Synthetix', 'symbol': 'SNX'}, {'name': 'dYdX', 'symbol': 'DYDX'}, {'name': 'GMX', 'symbol': 'GMX'}], 'LSD & LSDFi': [{'name': 'Lido DAO', 'symbol': 'LDO'}, {'name': 'Pendle', 'symbol': 'PENDLE'}, {'name': 'Rocket Pool', 'symbol': 'RPL'}, {'name': 'SSV Network', 'symbol': 'SSV'}], 'Restaking': [{'name': 'AltLayer', 'symbol': 'ALT'}, {'name': 'Pendle', 'symbol': 'PENDEL'}, {'name': 'TENET', 'symbol': 'TENET'}, {'name': 'Restake Finance', 'symbol': 'RSTK'}, {'name': 'Picasso', 'symbol': 'PICA'}], 'POW': [{'name': 'Kaspa', 'symbol': 'KAS'}, {'name': 'Ethereum Classic', 'symbol': 'ETC'}, {'name': 'Litecoin', 'symbol': 'LTC'}, {'name': 'Doge', 'symbol': 'DOGE'}, {'name': 'Conflux', 'symbol': 'CFX'}], 'Layer 2': [{'name': 'Optimism', 'symbol': 'OP'}, {'name': 'Arbitrum', 'symbol': 'ARB'}, {'name': 'Starknet', 'symbol': 'STRK'}, {'name': 'Manta Pacific', 'symbol': 'MANTA'}, {'name': 'Metis', 'symbol': 'METIS'}], 'NFT': [{'name': 'Blur', 'symbol': 'BLUR'}, {'name': 'LooksRare', 'symbol': 'LOOKS'}, {'name': 'X2Y2', 'symbol': 'X2Y2'}], 'Gaming': [{'name': 'Immutable', 'symbol': 'IMX'}, {'name': 'GALA', 'symbol': 'GALA'}, {'name': 'Ronin', 'symbol': 'RON'}, {'name': 'Magic', 'symbol': 'MAGIC'}, {'name': 'WEMIX', 'symbol': 'WEMIX'}, {'name': 'BEAM', 'symbol': 'BEAM'}, {'name': 'Pixels', 'symbol': 'PIXEL'}, {'name': 'Heroes of Mavia', 'symbol': 'MAVIA'}, {'name': 'Shrapnel', 'symbol': 'SHRAP'}], 'Games Guild': [{'name': 'Merit Circle', 'symbol': 'MC'}, {'name': 'Yield Guild Games', 'symbol': 'YGG'}, {'name': 'GuildFi', 'symbol': 'GF'}, {'name': 'indiGG', 'symbol': 'INDI'}], 'AI': [{'name': 'Bittensor', 'symbol': 'TAO'}, {'name': 'Fetch.ai', 'symbol': 'FET'}, {'name': 'Render Network', 'symbol': 'RNDR'}, {'name': 'Worldcoin', 'symbol': 'WLD'}, {'name': 'Autonolas', 'symbol': 'OLAS'}], '元宇宙': [{'name': 'The Sandbox', 'symbol': 'SAND'}, {'name': 'Axie Infinity ', 'symbol': 'AXS'}, {'name': 'Internet Computer', 'symbol': 'ICP'}, {'name': 'Mobox', 'symbol': 'MBOX'}, {'name': 'Worldcoin', 'symbol': 'WLD'}], 'COSMOS': [{'name': 'COSMOS Hub', 'symbol': 'ATOM'}, {'name': 'Injective', 'symbol': 'INJ'}, {'name': 'Celestia', 'symbol': 'TIA'}, {'name': 'Sei', 'symbol': 'SEI'}, {'name': 'JUNO', 'symbol': 'JUNO'}, {'name': 'Osmosis', 'symbol': 'OSMO'}, {'name': 'Kujira', 'symbol': 'KUJI'}], 'Bot': [{'name': 'Unibot', 'symbol': 'UNIBOT'}, {'name': 'Banana Gun', 'symbol': 'BANANA'}, {'name': 'AimBot', 'symbol': 'AIMBOT'}], '存储': [{'name': 'Filecoin', 'symbol': 'FIL'}, {'name': 'Arweave', 'symbol': 'AR'}, {'name': 'BitTorrent', 'symbol': 'BTT'}, {'name': 'Storj', 'symbol': 'STORJ'}], 'DePIN': [{'name': 'Helium', 'symbol': 'HNT'}, {'name': 'Helium Mobile', 'symbol': 'MOBILE'}, {'name': 'WiFi Map', 'symbol': 'WIFI'}, {'name': 'Hivemapper', 'symbol': 'HIVE'}, {'name': 'IoTeX', 'symbol': 'IOTX'}], 'Dev Platform': [{'name': 'The Graph', 'symbol': 'GRT'}, {'name': 'Covalent', 'symbol': 'CQT'}, {'name': 'Gelato Network', 'symbol': 'GEL'}, {'name': 'Ankr', 'symbol': 'ANKR'}], 'CEX Token': [{'name': 'Binance', 'symbol': 'BNB'}, {'name': 'OKX', 'symbol': 'OKB'}, {'name': 'Kucoin', 'symbol': 'KCS'}, {'name': 'Mainex', 'symbol': 'BGB'}, {'name': 'WOO', 'symbol': 'WOO'}, {'name': 'Gate.io', 'symbol': 'GT'}, {'name': 'Huobi', 'symbol': 'HT'}, {'name': 'MEXC', 'symbol': 'MX'}], 'Bridge': [{'name': 'Celer Network', 'symbol': 'CELR'}, {'name': 'Connext', 'symbol': 'NEXT'}, {'name': 'Hop Protocol', 'symbol': 'HOP'}, {'name': 'Multichain', 'symbol': 'MULTI'}], 'Oracle': [{'name': 'Pyth Network', 'symbol': 'PYTH'}, {'name': 'Chainlink', 'symbol': 'LINK'}, {'name': 'API3', 'symbol': 'API3'}], 'MEV': [{'name': 'Jito', 'symbol': 'JTO'}, {'name': 'Cow Protocol', 'symbol': 'COW'}], 'Fan Token': [{'name': 'ChilizX', 'symbol': 'CHZ'}, {'name': 'Santos FC Fan Token', 'symbol': 'SANTOS'}, {'name': 'Lazio Fan Token', 'symbol': 'LAZIO'}, {'name': 'FC Barcelona Fan Token', 'symbol': 'BAR'}, {'name': 'OG Fan Token', 'symbol': 'OG'}, {'name': 'Manchester City Fan Token', 'symbol': 'CITY'}, {'name': 'FC Porto', 'symbol': 'PORTO'}, {'name': 'Argentine Football Association Fan Token', 'symbol': 'ARG'}, {'name': 'AC Milan Fan Token', 'symbol': 'ACM'}, {'name': 'PRIMAL', 'symbol': 'PRIMAL'}, {'name': 'Paris Saint-Germain Fan Token', 'symbol': 'PSG'}, {'name': 'Alpine F1 Team Fan Token', 'symbol': 'FLPINE'}, {'name': 'Juventus Fan Token', 'symbol': 'JUV'}, {'name': 'AS Roma Fan Token', 'symbol': 'ASR'}, {'name': 'Galatasaray Fan Token', 'symbol': 'GAL'}, {'name': 'Atletico Madrid Fan Token', 'symbol': 'ATM'}, {'name': 'Arsenal Fan Token', 'symbol': 'AFC'}, {'name': 'Inter Milan Fan Token', 'symbol': 'INTER'}, {'name': 'Tottenham Hotspur FC Fan Token', 'symbol': 'SPURS'}], 'MEME': [{'name': 'Shiba Inu', 'symbol': 'SHIB'}, {'name': 'Bonk', 'symbol': 'BONK'}, {'name': 'Pepe', 'symbol': 'PEPE'}, {'name': 'dogewifhat', 'symbol': 'WIF'}, {'name': 'Coq Inu', 'symbol': 'COQ'}, {'name': 'Dogecoin', 'symbol': 'DOGE'}], 'ZK': [{'name': 'Polygon', 'symbol': 'MATIC'}, {'name': 'Mina Protocol', 'symbol': 'MINA'}, {'name': 'Metis', 'symbol': 'METIS'}, {'name': 'Immutable', 'symbol': 'IMX'}], 'RWA': [{'name': 'MakerDAO', 'symbol': 'MKR'}, {'name': 'Ondo', 'symbol': 'ONDO'}, {'name': 'TrueFi', 'symbol': 'TRU'}, {'name': 'Dusk', 'symbol': 'DUSK'}, {'name': 'Creditcoin', 'symbol': 'CTC'}, {'name': 'Polymesh', 'symbol': 'POLYX'}]}
    """
    workbook = openpyxl.load_workbook('板块分类.xlsx')
    sheet = workbook.active
    # 存储最终结果
    categories = {}
    # 遍历整个工作表
    category = None
    for row in sheet.iter_rows(values_only=True):
        c = row[0]
        if c == '板块':
            continue
        if c:
            category = c
        if not c:
            c = category
        project_name = row[1]
        symbol = row[2]
        item = {'name':project_name, 'symbol':symbol}
        if c in categories:
            c_old_list_value = categories[c]
            c_old_list_value.append(item)
            categories[c] = c_old_list_value
        else:
            categories[c] = [item]
    print(categories)
    categories_new = format_json(categories)
    print(categories_new)

    # 关闭工作簿
    workbook.close()

if __name__ == '__main__':
    format_origin_data()