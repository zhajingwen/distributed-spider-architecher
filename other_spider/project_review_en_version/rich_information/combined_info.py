import logging
# from .dex_volume import Volume24hCex
from .website_views import WebsiteVisiters
from .twitter import Twitter
from .discord_ import Discord
from .raisedinfo_and_projectbio import RaisedBio
from .coingeck_url import CoingeckSearch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Combined Info')

def combined_information(data):
    """
    丰富信息维度
    """
    try:
        # 补充网站流量
        visiters_content = None
        website = data['link']['website']
        if website:
            visiters_content = WebsiteVisiters(website).visiters()
        data['social']['website_visiters'] = visiters_content
    except:
        logger.error(f'补充网站流量异常：{data}')
    try:
        # 获取twitter粉丝量
        twitter_url = data['link']['twitter']
        twitter_followers_count = None
        if twitter_url:
            twitter_split = twitter_url.split('/')
            twitter_username = twitter_split[-1]
            if not twitter_username:
                twitter_username = twitter_split[-2]
            twitter_followers_count = Twitter().followers_count(twitter_username)
        data['social']['twitter_followers'] = twitter_followers_count
    except:
        logger.error(f'twitter粉丝量补充异常：{data}')
    try:
        # 获取discord人数
        discord_url = data['link']['discorad']
        if discord_url:
            total_members, online_members = Discord().discord(discord_url)
            data['social']['discord_total_members'] = total_members
            data['social']['discord_online_members'] = online_members
    except:
        logger.error(f'discord人数补充异常：{data}')
    try:
        # 获取项目一级市场融资信息
        name = data['base_info']['name']
        if not name:
            name = data['base_info']['symbol']
        raised_volume,project_bio = RaisedBio().raised_and_bio(name)
        data['base_info']['raised_volume'] = raised_volume
        data['base_info']['project_bio'] = project_bio
    except:
        logger.error(f'融资信息采集异常：{data}')
    try:
        symbol = data['base_info']['symbol']
        coingecko_url = CoingeckSearch(symbol).get_url()
        data['link']['coingecko_url'] = coingecko_url
    except:
        logger.error(f'coingecko匹配异常：{data}')
    return data