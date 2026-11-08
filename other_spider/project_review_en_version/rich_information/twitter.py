import os
import requests, json


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
        """
        刷新请求头签名信息
        """
        resp1 = requests.post("https://api.twitter.com/oauth2/token", params={"grant_type": "client_credentials"},
                              auth=(os.getenv('TWITTER_CONSUMER_KEY', ''), os.getenv('TWITTER_CONSUMER_SECRET', ''))).json()
        self.headers["Authorization"] = f"Bearer {resp1['access_token']}"
        resp2 = requests.post("https://api.twitter.com/1.1/guest/activate.json", headers=self.headers).json()
        self.headers["x-guest-token"] = resp2["guest_token"]
        return {"access_token": resp1['access_token'], "guest_token": resp2["guest_token"]}

    def get_user_profile(self, user_name):
        # 刷新请求头
        self.refresh_headers()
        # 获取用户信息
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

    def followers_count(self, user_name):
        """
        获取粉丝量
        """
        data = self.get_user_profile(user_name)
        try:
            followers_count = data['data']['user']['result']['legacy']['followers_count']
            followers_count = self.num_transform(followers_count)
        except:
            followers_count = 'X账号异常'
        return followers_count