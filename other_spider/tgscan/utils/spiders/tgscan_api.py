# import requests
# import os
# import logging
# from retry import retry
#
# env = os.environ.get('env')
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger('TGscan API')
#
# class Spider:
#     def __init__(self):
#         if env == 'prod':
#             self.search_url = 'https://api.tgdev.io/tgscan/v1/search'
#             # similar_url = 'https://api.tgdev.io/tgscan/v1/chat/similar'
#             # check_url = 'https://api.tgdev.io/tgscan/v1/user/check'
#             self.api_key = '<API_KEY_TGSCAN>'
#         else:
#             self.search_url = 'https://api.tgdev.io/tgscan/v1/test/search'
#             # similar_url = 'https://api.tgdev.io/tgscan/v1/test/chat/similar'
#             # check_url = 'https://api.tgdev.io/tgscan/v1/test/user/check'
#             self.api_key = '<API_KEY_TGSCAN_2>'
#         self.check_username_url = 'https://api.tgdev.io/tgscan/v1/user/check'
#
#     def split_content(self, text, split_pattern):
#         """
#         telegram限制文本长度4096，大于这个阈值无法发送成功，需要进行切割操作
#         split_pattern: 切割规则 \n
#         """
#         if len(text) > 3000:
#             paragraphs = []
#             # 切割后的段落列表
#             rows = text.split(split_pattern)
#             paragraph = ''
#             for row in rows:
#                 # 以行为单位进行分段
#                 paragraph += f'{row}{split_pattern}'
#                 # 达到段落阈值，则放入容器 paragraphs
#                 if len(paragraph) > 3000:
#                     paragraphs.append(paragraph)
#                     # 初始化
#                     paragraph = ''
#         else:
#             paragraphs = [text]
#         return paragraphs
#
#     def html(self, data):
#         """
#         html 格式化
#         """
#         result = data['result']
#         user = result['user']
#         username = user['username']
#         nick_name = user['first_name']
#         last_name = user['last_name']
#         if last_name:
#             nick_name = f'{nick_name} {last_name}'
#         # 用户基本信息
#         user_info = f"<b>用户ID：</b>@{username}\n<b>昵称：</b>{nick_name}\n\n"
#         # 用户历史信息
#         histry_user_info = "<b>曾用名（ID）：</b>\n"
#         # list
#         usernames_history = result['username_history']
#         if usernames_history:
#             for username_h in usernames_history:
#                 row = f'{username_h["username"]} {username_h["date"]}\n'
#                 histry_user_info += row
#             histry_user_info += '\n'
#         else:
#             histry_user_info += "无\n\n"
#         # 群总数
#         known_num_groups = result['meta']['known_num_groups']
#         num_groups = result['meta']['num_groups']
#         logger.info(f'known_num_groups: {known_num_groups}')
#         logger.info(f'num_groups: {num_groups}')
#         groups = result['groups']
#         # 群总数 + 群清单
#         group_list = f'<b>群总数：</b><i>{num_groups}</i>\n'
#         # 群清单
#         if groups:
#             for g in groups:
#                 username = g['username']
#                 title = g['title']
#                 row = f'<b>{title}</b> @{username}\n\n'
#                 group_list += row
#         # 拼接
#         content = user_info + histry_user_info + group_list
#         # 切片 为markdown服务，这个有个问题，markdown总会因为一些特殊字符而解析异常，不推荐使用mardown
#         content_split_list_html = self.split_content(content, '\n')
#         return content_split_list_html
#
#     @retry(tries=3)
#     def req(self, user_name, url, headers):
#         """
#         发起search 和 check请求
#         """
#         user_name = user_name.replace('@', '')
#         # user_name 不能携带 @
#         params = {
#             'query':user_name
#         }
#         logger.info(f'post: {url}')
#         res = requests.post(url, headers=headers, data=params)
#         logger.info(f'response {res.status_code}: {url}')
#         data = res.json()
#         status = data['status']
#         if status != 'ok':
#             message = data['result']['message']
#             logger.error(f'查询失败: {message}')
#             return
#         else:
#             return data
#
#     def check(self, user_name):
#         """
#         检测用户是否存在，检测是否有群
#         该方法只支持生产环境的 api_key
#         return False, 0, 1, 2   (只有2才会执行search操作)
#         """
#         api_key = '<API_KEY_TGSCAN>'
#         headers = {
#             'Api-Key': api_key
#         }
#         data = self.req(user_name, self.check_username_url, headers)
#         if data:
#             result = data['result']
#             # 查询不到用户时，才会存在这个key
#             if 'message' in result:
#                 # 表示用户的username错误
#                 return 0
#             else:
#                 known_num_groups = result['meta']['known_num_groups']
#                 if known_num_groups == 0:
#                     # 未加入任何群
#                     return 1
#                 else:
#                     # 加入了群
#                     return 2
#         # 没有该用户
#         else:
#             return False
#
#     def search_(self, user_name):
#         """
#         通过username查询群关系
#         """
#         headers = {
#             'Api-Key': self.api_key
#         }
#         data = self.req(user_name, self.search_url, headers)
#         if data:
#             html_list = self.html(data)
#             return html_list
#         else:
#             return
#
#     def search(self, user_name):
#         """
#         先进性校验用户名合法性
#         合法则进行 username 查询接口调用，并返回结果
#         """
#         search_result = None
#         check = self.check(user_name)
#         if check == False:
#             logger.error(f'check 用户名错误：{user_name}')
#         elif check == 0:
#             logger.error(f'check 用户名错误：{user_name}')
#         elif check == 1:
#             logger.error(f'check 该用户未加入任何群：{user_name}')
#         elif check == 2:
#             search_result = self.search_(user_name)
#         else:
#             logger.error(f'check 用户校验发生未知错误：{user_name}')
#         return search_result
