import logging
import re
# env = os.environ.get('env')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Content Format')


class Format:
    """
    格式化查询结果为 markdown语法或者 HTML
    将长文本分片
    """
    def split_content(self, text, split_pattern):
        """
        telegram限制文本长度4096，大于这个阈值无法发送成功，需要进行切割操作
        split_pattern: 切割规则 \n
        """
        if len(text) > 3000:
            paragraphs = []
            # 切割后的段落列表
            rows = text.split(split_pattern)
            paragraph = ''
            for row in rows:
                # 以行为单位进行分段
                paragraph += f'{row}{split_pattern}'
                # 达到段落阈值，则放入容器 paragraphs
                if len(paragraph) > 3000:
                    paragraphs.append(paragraph)
                    # 初始化
                    paragraph = ''
            # 最后一个段落，其不满足大于3000的标准，在这里补漏
            if paragraph not in paragraphs:
                paragraphs.append(paragraph)
        else:
            paragraphs = [text]
        return paragraphs

    def html(self, data):
        """
        html 格式化
        return: list ['xx','xx']
        """
        result = data['result']
        user = result['user']
        username = user['username']
        nick_name = user['first_name']
        last_name = user['last_name']
        if last_name:
            nick_name = f'{nick_name} {last_name}'
        # 用户基本信息
        user_info = f"<b>ID：</b>@{username}\n<b>昵称：</b>{nick_name}\n\n"
        # 用户历史信息
        histry_user_info = "<b>曾用名（ID）：</b>\n"
        # list
        usernames_history = result['username_history']
        if usernames_history:
            for username_h in usernames_history:
                row = f'{username_h["username"]} {username_h["date"]}\n'
                histry_user_info += row
            histry_user_info += '\n'
        else:
            histry_user_info += "无\n\n"
        # 群总数
        known_num_groups = result['meta']['known_num_groups']
        num_groups = result['meta']['num_groups']
        logger.info(f'known_num_groups: {known_num_groups}')
        logger.info(f'num_groups: {num_groups}')
        groups = result['groups']
        # 群总数 + 群清单
        group_list = f'<b>群总数：<i><u>{num_groups}</u></i></b>\n'
        # 群清单
        if groups:
            for g in groups:
                username = g['username']
                title = g['title']
                # <> 无法被解析，需要剔除，否则报错
                title = re.sub(r'<.*?>', '', title)
                row = f'<a href="https://t.me/{username}"><b>{title}</b></a>\n\n'
                group_list += row
        # 拼接
        content = user_info + histry_user_info + group_list
        content_split_list_html = self.split_content(content, '\n')
        return content_split_list_html

    def format(self, data):
        # markdown总会因为一些特殊字符而解析异常，不推荐使用mardown
        return self.html(data)
