from .entrance import Main

def run(spider_name):
    # 当CMC有数据的时候从cmc获取，cmc没有数据的时候从coingecko获取
    Main().run()