import os
import requests, json


class Spider:

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

    def get_user_profile(self, user_name):
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

    def run(self, user_name):
        data = self.get_user_profile(user_name)
        try:
            followers_count = data['data']['user']['result']['legacy']['followers_count']
        except:
            followers_count = 'X账号异常'
        return followers_count

