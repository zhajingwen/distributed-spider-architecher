- google指数官方查询页面
https://trends.google.com/trends/explore?date=all&geo=US&q=posture%20corrector
- 指数数据的官方接口
https://trends.google.com/trends/api/widgetdata/multiline?hl=zh-CN&tz=-480&req=%7B%22time%22:%222004-01-01+2022-08-02%22,%22resolution%22:%22MONTH%22,%22locale%22:%22zh-CN%22,%22comparisonItem%22:%5B%7B%22geo%22:%7B%22country%22:%22US%22%7D,%22complexKeywordsRestriction%22:%7B%22keyword%22:%5B%7B%22type%22:%22BROAD%22,%22value%22:%22posture+corrector%22%7D%5D%7D%7D%5D,%22requestOptions%22:%7B%22property%22:%22%22,%22backend%22:%22IZG%22,%22category%22:0%7D,%22userConfig%22:%7B%22userType%22:%22USER_TYPE_LEGIT_USER%22%7D%7D&token=APP6_UEAAAAAYuoh_Enxg6KDgt3rO6NkTMGFj3Oko5Qf&tz=-480

### 官方接口
主页有详细的说明文档

---
- 目前来看有开源的解决方案
>该种解决方案也是基于逆向破解的思路，如果官方接口发生变化也需要更新
> github地址：https://github.com/GeneralMills/pytrends
```commandline
pip install pytrends
```

- 目前来讲搜索的web页面提供了多种类型的数据展示，展示的维度也比较多；基本上也能够通过接口获取。
> 但是目前只需要拿到multiline的接口数据
- 关于搜索词来讲，web页面支持同时搜索多个关键词，目前测试了两个；
> 多个关键词同时搜索，只需要请求一次的接口数据
- 接口数据解析：
> default:timelineData >得到的数据结构是个列表，该列表的长度是233
- 修改源码：
> '/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages/pytrends
> 目录下request.py文件 中的417 or 466行   return final 改为 return req_json

- 2023-10-18 luminati数据中心的代理IP不可用，切换成了ISP
