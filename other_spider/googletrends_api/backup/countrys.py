countrys = """东亚区域：韩国、日本、中国
港澳台区域：香港、澳门、台湾
东南亚区域：越南、泰国、印度尼西亚、马来西亚、新加坡、缅甸、菲律宾、柬埔寨
南亚区域：印度、巴基斯坦
英文区域：美国、英国、加拿大、澳大利亚
CIS区域：俄罗斯、乌克兰、白俄罗斯、哈萨克斯坦、乌兹别克斯坦
欧洲区域：土耳其、德国、法国、意大利、西班牙、荷兰、瑞士、波兰、比利时
中东区域：阿拉伯联合酋长国、沙特阿拉伯、卡塔尔、以色列
拉丁美洲区域：阿根廷、巴西、墨西哥、乌拉圭、智利、哥伦比亚
非洲区域：尼日利亚、南非、埃及、摩洛哥、阿尔及利亚"""
c_a = {}
for row in countrys.strip().split('\n'):
    if row.strip():
        orin = row.strip().split('：')
        area = orin[0]
        cs = orin[1]
        cs = cs.strip().split('、')
        for c in cs:
            c_a[c] = {'area':area}
print(c_a)
from other_spider.googletrends_api.backup.country_charset import data

for c in c_a:
    c_a[c]['geo'] = data[c]
print(c_a)