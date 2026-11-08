
def cut_bio(content):
    """
    将项目简介控制在150个字符内
    """
    if not content:
        return content
    content_list = content.split(' ')
    if len(content_list) > 150:
        content_list_new = content[:150]
        reversed_list = list(reversed(content_list_new))
        split_point = 0
        for index, word in enumerate(reversed_list):
            if '.' in word or '?' in word or '!' in word:
                split_point = index
                break
        cleaned_reversed_list = reversed_list[split_point:]
        cleaned_list = list(reversed(cleaned_reversed_list))
        content = ' '.join(cleaned_list)
    return content

