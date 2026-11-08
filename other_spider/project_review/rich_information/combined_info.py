import logging
from traceback import format_exc
from .discord_ import Discord
# from .raisedinfo_and_projectbio import RaisedBio
from .funding import funding_info
# from .coingeck_url import CoingeckSearch
from .telegram_members import Telegram
from .quickintel import Quickintel
# from other_spider.project_review.rich_information.twitter import Twitter
from .twitter import Twitter
# from other_spider.project_review.rich_information.solana.solana_holders_hlius import Hlius
from other_spider.project_review.rich_information.solana.solana_birdeye_security import BirdeyeSecurity
from other_spider.project_review.rich_information.solana.rugcheck_lplocked_top10addresses import Rugcheck

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Combined Info')

def combined_information(data, scraper_twitter):
    """
    丰富信息维度
    """
    # try:
    #     # 补充网站流量
    #     visiters_content = None
    #     website = data['link']['website']
    #     if website:
    #         visiters_content = WebsiteVisiters(website).visiters()
    #     data['social']['最近一个月官网访问量'] = visiters_content
    # except:
    #     logger.error(f'补充网站流量异常：{data}')
    try:
        # 获取twitter粉丝量+前10条帖子的平均流量
        twitter_url = data['link']['twitter']
        twitter_followers_count = None
        # twitter_average_tweet_views = None
        if twitter_url:
            twitter_followers_count = Twitter().run(twitter_url, scraper_twitter)
        data['social']['twitter粉丝数'] = twitter_followers_count
        # data['social']['twitter前10条帖子平均流量'] = twitter_average_tweet_views
    except:
        logger.error(f'twitter数据补充异常：{data}，{format_exc()}')
    try:
        # 获取discord人数
        discord_url = data['link']['discoard']
        if discord_url:
            total_members, online_members = Discord().discord(discord_url)
            data['social']['discord用户数'] = total_members
            data['social']['discord在线人数'] = online_members
    except:
        logger.error(f'discord人数补充异常：{data}')
    try:
        data = funding_info(data)
        # 获取项目一级市场融资信息
    except:
        logger.error(f'融资信息采集异常：{data}')
        logger.error(f'融资信息采集异常：{format_exc()}')
    # try:
    #     symbol = data['base_info']['symbol']
    #     coingecko_url = CoingeckSearch(symbol).get_url()
    #     data['link']['coingecko_url'] = coingecko_url
    # except:
    #     logger.error(f'coingecko匹配异常：{data}')
    try:
        # 获取telegram群组人数
        telegram_url = data['link']['telegram']
        if telegram_url:
            # None or tuple
            result = Telegram().members(telegram_url)
            if result:
                total_members, online_members = result
                data['social']['telegram用户数'] = total_members
                data['social']['telegram在线人数'] = online_members
    except:
        logger.error(f'telegram人数补充异常：{data}，{format_exc()}')
    # quickintel合约风险检测 + 新增合约检测链接 + TOP10持币地址
    try:
        data = Quickintel().quickintel(data)
    except:
        logger.error(f'quickintel合约风险检测异常：{data}')
    # 添加BSC + ehter 浏览器链接
    try:
        chain = data['base_info']['公链']
        address = data['base_info']['代币地址']
        if chain == 'ether':
            chain_scan_url = f'https://etherscan.io/address/{address}'
            data['link']['公链浏览器'] = chain_scan_url
        if chain == 'bsc':
            chain_scan_url = f'https://bscscan.com/address/{address}'
            data['link']['公链浏览器'] = chain_scan_url
    except:
        logger.error(f'公链浏览器添加异常：{data}')
    # # 当是solana链的时候，通过Hlius API 请求TOP10 holders
    # try:
    #     data = Hlius().top10_addresses(data)
    # except:
    #     logger.error(f'Hlius 数据请求异常：{data}')
    # 当公链是solana的时候用birdeye进行合约检测
    try:
        data = BirdeyeSecurity().check(data)
    except:
        logger.error(f'birdeye 合约检测异常：{data}')
    # 当公链是solana的时候用rugcheck获取锁仓数据 + TOP10 holders
    try:
        data = Rugcheck().lplocked_percent_mixed_top10_addresses(data)
    except:
        logger.error(f'rugcheck 数据获取异常：{data}')
    return data