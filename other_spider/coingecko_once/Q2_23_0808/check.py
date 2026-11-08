done = """fore-protocol
pepe-2-0
snkrz-fit
hamsters
stader
cogito-protocol
adreward
verse-bitcoin
gains-network
ilcapo
dione
octo-gaming
shibarium-perpetuals
pogai
project-galaxy
mass-vehicle-ledger
pulsechain
walken
liquity
ribbit-meme
catgirl
space-id
wifi
abyss-world
the-virtua-kolect
access-protocol
bitmex-token
sharbi
alchemy-pay
bhnetwork
drac-ordinals
chaingpt
chad-coin
oggy-inu
affyn
l
reality-metaverse
milady-meme-coin
reign-of-terror
tcg-verse#markets
mythos
pay-coin
xcad-network-play
velodrome-finance
white-whale
veno-finance
playa3ull-games
custodiy
areon-network
ronin
nals
bullbear-ai
axelar
pando
veritise
sponge-f08b2fe4-9d9c-47c3-b5a0-84c2ac3bbbff
wall-street-baby
zzz
suipad
galaxia
sperax
litlab-games
multichain
mongcoin
zoid-pay
ben-2
degenreborn
myria
majo
karate-combat
delysium
echelon-prime
bear-inu
brn-metaverse
dinolfg
suia
arbdoge-ai
helium
3-kingdoms-multiverse
stella-fantasy-token
meta-fps
gpt-guru
limewire-token
alaska-gold-rush
stonksdao
agility
stp-network
iron-fish
xana
crown-token-77469f91-69f6-44dd-b356-152e2c39c0cc
pip
zkapes-token
canto
klima-dao
propchain
spheresxs
coinzix-token
the-unfettered-souls
aishiba
wojak
vela-token
weway
pendle
palmswap
lord-of-dragons
playzap
camelot-token
wistaverse
osmosis
arbipad
izumi-finance
floki
pooh
quantum-resistant-ledger
ai-code
kaspa
turbo
iskra-token
ai-network
waifuai
ordinals
treecle
tangible
true-usd
degis
mr-potato
pleb-token
hibakc
metfi
pepegpt
clips
yesports
gelato
vmpx
project-xeno
velo
liquid-staking-derivative
tomtomcoin
dimo
floki-ceo
favor
flappymoonbird
aped
pmg-coin
pepe
cetus-protocol
turbos-finance
bob-token
fairerc20
orbofi-ai
tominet
ignore-fud
bananatok
sui
wiki-cat
eldarune
zizy
love-hate-inu
omega-network
calorie
tamadoge
bsv
tenet-1b000f7b-59cb-4e06-89ce-d62b32d362b9
metabeat
fourcoin
haha
baby-doge-coin
profit-blue
the-qwan
bware-infra
refund
finblox
suiswap
noot-ordinals
biso
lbvivi
selfcrypto
yachtingverse
maverick-protocol
unleashclub
spider-man
metatime-coin
ethlas"""
done = done.strip().split('\n')
failed = []
import json
import requests
from lxml import etree
def get_symbol(url):
    headers = {
        'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    print(f'request: {url}')
    res = requests.get(url,headers=headers)
    tree = etree.HTML(res.text)
    symbol = tree.xpath('//div[@class="tw-m-0 tw-text-base tw-break-all"]/span[2]/text()')
    print(symbol)


def check():
    path = 'other_spider/coingecko_once/Q2_23_0808/'

    with open(f'{path}Q2_allcoins_incoingecko')as f:
        coins = f.read().strip()
        coins_list = json.loads(coins)
    coins_id_json = {}
    coins_symbol_json = {}
    coins_names_json = {}
    for item in coins_list:
        coins_id_json[item['id']] = item
        coins_symbol_json[item['symbol']] = item
        coins_names_json[item['name'].lower()] = item
    id_urls_json = {}
    # id_error = []
    # done = ['stader', 'cogito-protocol', 'adreward', 'verse-bitcoin', 'gains-network', 'ilcapo', 'dione', 'octo-gaming', 'edu-coin', 'shibarium-perpetuals', 'pogai', 'project-galaxy', 'mass-vehicle-ledger', 'pulsechain', 'walken', 'liquity', 'ribbit-meme', 'catgirl', 'space-id', 'wifi', 'abyss-world', 'the-virtua-kolect', 'access-protocol', 'bitmex-token', 'sharbi', 'pizabrc', 'alchemy-pay', 'bhnetwork', 'drac-ordinals', 'chaingpt', 'chad-coin', 'oggy-inu', 'affyn', 'l', 'reality-metaverse', 'milady-meme-coin', 'reign-of-terror', 'tcg-verse#markets', 'mythos', 'pay-coin', 'xcad-network-play', 'velodrome-finance', 'white-whale', 'veno-finance', 'tether-eurt', 'playa3ull-games', 'custodiy', 'areon-network', 'ronin', 'nals', 'bullbear-ai', 'axelar', 'tezos-pepe', 'pando', 'veritise', 'sponge-f08b2fe4-9d9c-47c3-b5a0-84c2ac3bbbff', 'alexgo', 'wall-street-baby', 'zzz', 'suipad', 'stepn', 'galaxia', 'sperax', 'litlab-games', 'multichain', 'mongcoin', 'zoid-pay', 'ben-2', 'degenreborn', 'myria', 'majo', 'karate-combat', 'delysium', 'echelon-prime', 'bear-inu', 'rektskulls', 'brn-metaverse', 'dinolfg', 'suia', 'arbdoge-ai', 'helium', 'freicoin', '3-kingdoms-multiverse', 'stella-fantasy-token', 'hello-labs', 'float-protocol', 'meta-fps', 'gpt-guru', 'limewire-token', 'alaska-gold-rush', 'stonksdao', 'agility', 'stp-network', 'iron-fish', 'xana', 'crown-token-77469f91-69f6-44dd-b356-152e2c39c0cc', 'pip', 'zkapes-token', 'canto', 'klima-dao', 'propchain', 'spheresxs', 'coinzix-token', 'the-unfettered-souls', 'aishiba', 'wojak', 'vela-token', 'weway', 'pendle', 'palmswap', 'lord-of-dragons', 'blueart', 'playzap', 'camelot-token', 'wistaverse', 'osmosis', 'arbipad', 'izumi-finance', 'floki', 'pooh', 'quantum-resistant-ledger', 'ai-code', 'kaspa', 'turbo', 'iskra-token', 'ai-network', 'waifuai', 'ordinals', 'treecle', 'tangible', 'true-usd', 'degis', 'mr-potato', 'pleb-token', 'hibakc', 'metfi', 'pepegpt', 'clips', 'yesports', 'gelato', 'vmpx', 'project-xeno', 'velo', 'liquid-staking-derivative', 'tomtomcoin', 'dimo', 'floki-ceo', 'favor', 'dons', 'flappymoonbird', 'solana-inu', 'aped', 'pmg-coin', 'pepe', 'cetus-protocol', 'turbos-finance', 'bob-token', 'memeverse', 'fairerc20', 'orbofi-ai', 'tominet', 'ignore-fud', 'bananatok', 'sui', 'wiki-cat', 'eldarune', 'zizy', 'love-hate-inu', 'omega-network', 'calorie', 'tamadoge', 'bsv', 'tenet-1b000f7b-59cb-4e06-89ce-d62b32d362b9', 'metabeat', 'fourcoin', 'haha', 'baby-doge-coin', 'profit-blue', 'the-qwan', 'bware-infra', 'refund', 'finblox', 'suiswap', 'noot-ordinals', 'biso', 'lbvivi', 'selfcrypto', 'yachtingverse', 'maverick-protocol', 'unleashclub', 'spider-man', 'metatime-coin', 'ethlas']
    # done2 = ['sakai-vault', 'storepay', 'shaun-inu', 'sell-token', 'nothing-token', 'flexmeme', 'pepera', 'zkdoge', 'qlindo', 'milk-alliance', 'magic-oi-money', 'x7-coin', 'kabosu-arbitrum', 'naetion', 'athos-finance', 'pepexl', 'style-protocol', 'wistaverse', 'golcoin', 'topdown-survival-shooter', 'muratiai', 'mooi-network', 'acorn-protocol', 'portuma', 'leandro-lopes', 'pogai', 'edfi', 'dextf', 'smardex', 'bitcoinpepe', 'mememe', 'doge-blue', 'qitmeer-network', 'xodex', 'kripto', 'aptopad', 'tether-gold', 'shido', 'esco-coin', 'vow', 'nordek', 'monkeys-token', 'tabtrader', 'troll-face', 'scooby-doo', 'xrp-classic-new', 'fluus', 'trillioner', 'octavus-prime', 'gleec-coin', 'dream-machine-token', 'perion', 'chain-guardians', 'dynex', 'i-love-snoopy', 'uniwhale', 'blockchain-bets', 'rubic', 'centcex', 'derp-coin', 'mfet', 'pomerium', 'kek', 'spheroid-universe', 'king', 'gode-chain', 'teddy-doge', 'cryptopirates', 'ubxs-token', 'sonic-inu', 'pepeai', 'arix', 'orbofi-ai', 'hold-vip', 'bobo-coin', 'ls-coin', 'six-network', 'wefi-finance', 'wall-street-baby', 'fomo-eth', 'doge-ceo', 'hypercycle', 'vaiot', 'airtor-protocol', 'arbswap', 'sharbi', 'cheelee', 'kcal', 'triall', 'astrafer', 'me-gusta', 'safe-anwang', 'pink-bnb', 'bluesale', 'fasttoken', 'zenpandacoin', 'urdex-finance', 'blocksquare', 'peepo', '3d3d', 'kekya', 'spgbb', 'connectome', 'homer', 'soulsaver', 'astra-dao', 'suzuverse', 'vinlink', 'ultron', 'giant-mammoth', 'papi', 'relation-native-token', 'ordinex', 'marvellex-classic', 'pepe-coin-bsc', 'sui-launch-token', 'otterhome', 'kepple', 'bart-simpson-coin', 'roseon', 'hypergpt', 'gnome', 'noot', 'ppizza', 'leox', 'financie-token', 'aienglish', 'snek', 'web3camp', 'greg', 'rugame', 'maxity', 'algebra', 'wrapped-ordichains', 'apes-go-bananas', 'blockchaingames', 'mangoman-intelligent', 'metavault-dao', 'pepa-inu', 'rangers-fan-token', 'top-network', 'renq-finance', 'zknftex', 'antspace', 'galeon', 'planet-token', 'gemhub', 'disney', 'taboo-token', 'wewe', 'omax-token', 'the-nemesis', 'shib-original-vision', 'pomerium-ecosystem', 'hepton', 'mongol-nft', 'caw-ceo', 'renewable-energy', 'games-for-a-living', 'platform-of-meme-coins', 'unidef', 'bistroo']
    ids_error = ['fortune-token', 'joseon-mun', 'stella', 'combo', 'global-digital-cluster-coin', 'function-x',
                 'work-quest', 'layerai', 'bware', 'global-fan-token#markets', 'tenet', 'constellation', 'the-dons',
                 'maro', 'shrooms', 'cyberstella-stella', 'ben', 'sponge', 'funtoken', 'soonverse', 'aicoin',
                 'map-protocol', 'open-campus', 'koyo-token', 'euro-tether', 'navcoin', 'doubledice', 'rekt-arb',
                 'voltage-finance', 'alex-lab', 'so-col', 'metfi', 'angelblock', 'panther-protocol']
    result = {}
    for i in ids_error:
        if i in coins_symbol_json:
            id = coins_symbol_json[i]['id']
            id_urls_json[i] = id
        elif i in coins_names_json:
            id = coins_names_json[i]['id']
            id_urls_json[i] = id
        else:
            print(f'https://www.coingecko.com/en/coins/{i}')
            result[i] = ""
    # print(id_urls_json)
    #
    # with open(f'{path}jobs') as f:
    #     content = f.read().strip().split('\n')
    #     for row in content:
    #         url = row.strip()
    #         if url:
    #             id = url.split('https://www.coingecko.com/en/coins/')[-1]
    #             if '/' in id:
    #                 id = id.split('/')[0]
    #             # if id not in done:
    #                 # print(id)
    #             # self.id_urls[id] = url
    #             #     if id == 'https:':
    #             #         print(url)
    #             #     failed.append(id.strip())
    #             # id_urls_json[id] = url
    #             # if id not in coins_id_json:
    #             #     id_error.append(id)
    #                 # print(id)
    #             # if id in done:
    #             #     print(id)
    #             # if id not in done2:
    #             #     print(id)
    #
    #
    # # print(coins_id_json)
    # # print(list(set(failed)))
    # # unknown_list = []
    # ids_json = {}
    # for i in list(set(failed)):
    #     if i not in coins_id_json:
    #         if i not in coins_symbol_json:
    #             if i not in coins_names_json:
    #                 url = id_urls_json[i]
    #                 # print(i,url)
    #                 ids_json[i] = ""
                    # get_symbol(url)
    #                 # print(f'not in coingecko id {i}')
    #             else:
    #                 id = coins_names_json[i]['id']
    #                 ids_json[i] = id
    #
    #         else:
    #             id = coins_symbol_json[i]['id']
    #             ids_json[i] = id
    #
    # print(ids_json)

    # data = {
    #         "rekt-arb": "REKT",
    #         "piza-ordinals": "PIZA",
    #         "pepe-ordinals": "PEPE",
    #         "bank-ordinals": "BANK",
    #         "gomining-token": "GMT",
    #         "meme-ordinals": "MEME",
    #         "snkrz-force": "FRC",
    #         "inu-token-project": "INU",
    #         "blueart-token": "BLA",
    #         "hello#markets": "HELLO",
    #         "the-dons": "DONS",
    #         "euro-tether": "EURT",
    #         "open-campus": "EDU",
    #         "alex-lab": "ALEX"
    #     }

    # print(result)
    data = {
            "fortune-token": "FRTN",
            "global-digital-cluster-coin": "GDCC",
            "function-x": "FX",
            "work-quest": "WQT",
            "global-fan-token": "GLFT",
            "cyberstella-stella": "STL",
            "map-protocol": "MAP",
            "koyo-token": "KOY",
            "rekt-arb": "REKT",
            "voltage-finance": "VOLT",
            "panther-protocol": "ZKP"
        }
    result = {}
    for d in data:
        value = data[d].lower()
        new_id = coins_symbol_json[value]['id']
        result[d] = new_id
    print(result)
    # print(id_error)
    return result

        # else:
        #     # print(f'un known case {i}')
        #     unknown_list.append(i)
    # print(unknown_list)
        # print(i)
