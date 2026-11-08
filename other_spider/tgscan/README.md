webhook api: https://example.com/tgscan   已放弃用webhook的方式

---


| 目录                      | 说明                      |
|-------------------------|-------------------------|
| entrance.py             | TGscan项目入口，通过参数调用不同的机器人 |



## 依赖

```buildoutcfg

pip install python-telegram-bot

```

## 更新

---

- 新用户有用户名的送0.1U
- 新用户没有用户名的不送
- 推荐人推荐的新用户有用户名的才算是有效推荐，才会发放奖励，否则没有；