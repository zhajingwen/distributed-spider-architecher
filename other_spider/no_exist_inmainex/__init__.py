from .cmc_info import Spider
from .dextools_info import Dextools
from .export_data import Export
from .dex_cex_markets import Markets

def run(spidername):
    # 任务中 markets 和 address 可能都是空字符串
    # Spider().run()
    # Dextools().run()
    Export().run()
    # Markets().run()
