- 依赖项目
  https://github.com/vvanglro/cf-clearance
- 启动方式
```commandline
docker run -d --restart always --network host --name cf-server your-registry.example.com/spider:latest \
--host 0.0.0.0 --port 86 --workers 20

```
- docker地址
  - https://hub.docker.com/r/vvanglro/cf-clearance
  - your-registry.example.com/spider:latest 备份
- 生成cookies数据体样例
  ```
  {
      "id":id, # proxyURL的md5值 
      "proxy":httpxxxx,  # 指定ip的代理URL
      "ua":useragent,  # rpc返回的ua
      "cf":xxx, # rpc返回的cf_
      "timestamp":166433  # cf生成的时间，需要和当前调用的时间进行对比，如果超过30分钟，那就就丢球重新获取，否则再放回去，然后接着用该cf
  
  }
  ```
- 10个小时重启一次容器，来解决资源占用过高，和容器内进程失效的问题
- 2023年1月9号，dexfilter将cloud flare的服务关掉了，导致无cf_clearance 这个cookies key出现
- 在解决上述问题期间发现了个新库undetected_chromedriver，号称能绕过浏览器指纹检测；但是实际测试发现效果并不好；
比不上https://github.com/Xewdy444/CF-Clearance-Scraper该项目，undetected_chromedriver不仅加载速度慢，
而且无法获取cf_clearance
- 经过多次测试该项目仍然无法在容器内工作CF-Clearance-Scraper；和作者反馈了，作者却是正常的，无法复现问题；也真是奇怪
- 很奇怪一开始rpc成功率挺高的，跑着跑着rpc返回值就全都是失败了；真是让人费解啊；后来，试过了重启容器，杀掉后重开，都解决不了
```commandline
代理失败{'success': False, 'msg': 'cf challenge fail', 'user_agent': None, 'cookies': None}
```
- cookies半小时生成1次，确实对于IP的质量起到了很多的保障，如果休息时间过短，IP很容易跑废！