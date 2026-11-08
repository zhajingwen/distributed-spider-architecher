content = """SAGA ($SAGA)  trade open time: 2024-04-09 
Chainge ($XCHNG)  trade open time: 2024-04-09 
Katana Inu ($KATA)  trade open time: 2024-04-09 
Masa Network ($MASA)  trade open time: 2024-04-11 
Kitten Haimer ($KHAI)  trade open time: 2024-04-11 
Dappad ($APPA)  trade open time: 2024-04-11 
RichQUACK ($QUACK)  trade open time: 2024-04-12 
FOMO BULL CLUB ($FOMO)  trade open time: 2024-04-14 
MASSA ($MAS)  trade open time: 2024-04-15 
Nettensor ($NAO)  trade open time: 2024-04-15 
DisChain ($DIS)  trade open time: 2024-04-16 
Parcl ($PRCL)  trade open time: 2024-04-16 
Omni Network ($OMNI1)  trade open time: 2024-04-17 
AIT Protocol ($AIT)  trade open time: 2024-04-18 
Artrade token ($ATR)  trade open time: 2024-04-18 
Rarible ($RARI)  trade open time: 2024-04-18 
TEH EPIK DUCK ($EPIK)  trade open time: 2024-04-18 
Nervos Network ($CKB)  trade open time: 2024-04-19 
Merlin Chain ($MERL)  trade open time: 2024-04-19 
Roost Coin ($ROOST)  trade open time: 2024-04-19 
Alpha Quark Token ($AQT)  trade open time: 2024-04-19 
Alephium ($ALPH)  trade open time: 2024-04-20
Apu Apustaja ($APU)  trade open time: 2024-04-22 
AirTor Protocol ($ATOR)  trade open time: 2024-04-22 
"""


import re

items = []
for row in content.strip().split('\n'):
    name = re.findall('(.+?) \(', row.strip())[0].strip()
    symbol = re.findall('\$(.+?)\)', row.strip())[0].strip()
    trade_date = re.findall('trade open time: (.+)', row.strip())[0].strip()
    item = {
        'name':name,
        'symbol': symbol,
        'listing_date': trade_date,
    }
    items.append(item)
print(items)
