import os
import requests as requests_ori
from curl_cffi import requests
import logging
import json
from retry import retry
from utils.redisdb import redis_cli
from utils.rds import DataUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Twitter Followers')


class TwitterFollowers:
    def __init__(self):
        self.headers_twitter = {
        "Authorization": os.getenv('TWITTER_BEARER_TOKEN', ''),
        "x-guest-token": "",
        "x-twitter-active-user": "yes",
        "Referer": "https://twitter.com",
        "user-agent": "",
        }
        self.api_base = 'https://multichain-api.birdeye.so/solana/overview/token?address={}'
        self.redis_cli = redis_cli()
        self.redis_key = 'cloudflare:agentids'
        self.rds = DataUtils()

    @retry(tries=3, delay=10)
    def req(self, url):
        agent_id = self.redis_cli.spop(self.redis_key)
        logger.info(f'获取到agent-id: {agent_id}')
        headers = {
            "Agent-Id": agent_id,
            "Content-Type": "application/json",
            "Origin": "https://birdeye.so",
            "Page": "find_gems",
            "Referer": "https://birdeye.so/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        logger.info(f'Get: {agent_id}')
        res = requests.get(url, headers=headers, impersonate="chrome101")
        logger.info(f'Response {res.status_code}: {agent_id}')
        if res.status_code != 200:
            raise Exception(f'响应码异常：{res.status_code}')
        else:
            # 如果ID能获取到正常数据，再塞回redis
            self.redis_cli.sadd(self.redis_key, agent_id)
        return res.json()


    def refresh_headers(self):
        resp1 = requests_ori.post("https://api.twitter.com/oauth2/token", params={"grant_type": "client_credentials"},
                              auth=(os.getenv('TWITTER_CONSUMER_KEY', ''), os.getenv('TWITTER_CONSUMER_SECRET', ''))).json()
        self.headers_twitter["Authorization"] = f"Bearer {resp1['access_token']}"
        resp2 = requests_ori.post("https://api.twitter.com/1.1/guest/activate.json", headers=self.headers_twitter).json()
        self.headers_twitter["x-guest-token"] = resp2["guest_token"]
        return {"access_token": resp1['access_token'], "guest_token": resp2["guest_token"]}

    def user_info(self, user_name):
        # 刷新 请求头
        self.refresh_headers()
        return requests_ori.get("https://api.twitter.com/graphql/oUZZZ8Oddwxs8Cd3iW3UEA/UserByScreenName", headers=self.headers_twitter,
                            params={
                                "features": json.dumps({
                                    "hidden_profile_likes_enabled": False,
                                    "responsive_web_graphql_exclude_directive_enabled": True,
                                    "verified_phone_label_enabled": False,
                                    "subscriptions_verification_info_verified_since_enabled": True,
                                    "highlights_tweets_tab_ui_enabled": True,
                                    "creator_subscriptions_tweet_preview_api_enabled": True,
                                    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                                    "responsive_web_graphql_timeline_navigation_enabled": True
                                }),
                                "variables": json.dumps({
                                    "screen_name": user_name,
                                    "withSafetyModeUserFields": True
                                })
                            }).json()

    def num_transform(self, num):
        """
        数值转换成K M B
        """
        # 有可能是None
        if not num:
            return num
        # 10亿 转换成xxB
        if num > 1000000000:
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

    def get_followers(self, url):
        """
        获取twitter粉丝量
        url: 账号链接
        """
        # 解析出用户名
        user_name = url.replace('https://twitter.com/','').replace('/','').strip()
        logger.info(f'username: {user_name}')
        user_profile = self.user_info(user_name)
        try:
            user_profile_result = user_profile['data']['user']['result']
            try:
                followers_count = user_profile_result['legacy']['followers_count']
                followers_count = self.num_transform(followers_count)
            except:
                followers_count = 'X账号异常'
            return followers_count
        except:
            return ''

    def get_twitter_url(self, id):
        """
        获取twitter URL
        """
        birdeye_token_api = self.api_base.format(id)
        data = self.req(birdeye_token_api)
        if data:
            try:
                data = data['data']
                extensions = data['extensions']
                twitter = extensions.get('twitter')
            except:
                twitter = None
            return twitter
        return

    def followers(self, id):
        """
        根据 代币在birdeye的id，返回twitter粉丝量
        """
        twitter = self.get_twitter_url(id)
        if twitter:
            followers_count = self.get_followers(twitter)
            return followers_count
        return '无'

