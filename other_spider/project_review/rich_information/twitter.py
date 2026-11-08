import os
import requests
import json
import logging
from retry import retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Twitter')

class Twitter:

    def __init__(self):
        self.headers = {
        "Authorization": os.getenv('TWITTER_BEARER_TOKEN', ''),
        "x-guest-token": "",
        "x-twitter-active-user": "yes",
        "Referer": "https://twitter.com",
        "user-agent": "",
        }

    def refresh_headers(self):
        resp1 = requests.post("https://api.twitter.com/oauth2/token", params={"grant_type": "client_credentials"},
                              auth=(os.getenv('TWITTER_CONSUMER_KEY', ''), os.getenv('TWITTER_CONSUMER_SECRET', ''))).json()
        self.headers["Authorization"] = f"Bearer {resp1['access_token']}"
        resp2 = requests.post("https://api.twitter.com/1.1/guest/activate.json", headers=self.headers).json()
        self.headers["x-guest-token"] = resp2["guest_token"]
        return {"access_token": resp1['access_token'], "guest_token": resp2["guest_token"]}

    def user_info(self, user_name):
        # 刷新 请求头
        self.refresh_headers()
        return requests.get("https://api.twitter.com/graphql/oUZZZ8Oddwxs8Cd3iW3UEA/UserByScreenName", headers=self.headers,
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

    def every_item_views_num(self, item):
        """
        从每个帖子中抽取访问量数据，如果是转发的则返回None
        return: None or int
        """
        content = item.get('content')
        if not content:
            return
        itemContent = content.get('itemContent')
        if not itemContent:
            return
        views_ = itemContent['tweet_results']['result']['views']
        views = views_.get('count')
        if not views:
            return
        views = int(views)
        return views

    def get_tweets(self, user_id, scraper):
        """
        获取用户帖子信息
        """
        # 原始的是str，而需要的是int
        user_id = int(user_id)
        tweets = scraper.tweets([user_id], limit=10)
        instructions = tweets[1]['data']['user']['result']['timeline_v2']['timeline']['instructions']
        entries = instructions[2].get('entries')
        if not entries:
            for e in instructions:
                e_entries = e.get('entries')
                if e_entries:
                    entries = e_entries
        if not entries:
            logger.error(f'twitter帖子信息获取失败：userid: {user_id}')
            return
        try:
            all_views = 0
            views_count = 0
            for t in entries:
                if views_count > 9:
                    break
                # 解析出访问量
                try:
                    views = self.every_item_views_num(t)
                except:
                    logger.warning(f'帖子浏览量解析失败：{t}')
                    continue
                if not views:
                    continue
                views_count += 1
                all_views += views
            average_views = int(all_views/10)
            return average_views
        except:
            logger.error(f'twitter帖子信息获取失败(views count 异常)：userid: {user_id}')
            return

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

    def get_followers(self, url, scraper_twitter):
        # 解析出用户名
        user_name = url.replace('https://twitter.com/','').replace('/','').strip()
        logger.info(f'username: {user_name}')
        user_profile = self.user_info(user_name)
        logger.info(f'user_profile: {user_profile}')
        # 获取用户基本信息
        user_profile_result = user_profile['data']['user']['result']
        # 抽取出用户ID
        user_id = user_profile_result['rest_id']
        try:
            followers_count = user_profile_result['legacy']['followers_count']
            followers_count = self.num_transform(followers_count)
        except:
            followers_count = 'X账号异常'
        return followers_count

    # 有时候 refresh_headers 方法会失败，但是目前还不明确是什么原因
    @retry(tries=3, delay=6)
    def run(self, url, scraper_twitter):
        followers_count = self.get_followers(url, scraper_twitter)
        return followers_count