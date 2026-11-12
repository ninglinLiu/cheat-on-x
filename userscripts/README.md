# cheatx-exporter（油猴脚本）

在你**自己的浏览器**里浏览 x.com 时，记录页面已经加载的帖子数据，一键导出 CSV，交给 [`x-csv-import`](../adapters/perf-data/x-csv-import/README.md) 做复盘、对标导入和热点入池。

零 API 费用，不需要开发者账号。

## 它做什么、不做什么

**做**：
- x.com 自己会请求时间线、帖子详情、Explore 的数据。脚本在页面收到这些响应之后**读一份副本**，从中找出帖子对象，记下：曝光（views）、赞、转发、引用、回复、收藏、正文（含长帖全文）、发布时间、回复 / 引用关系、媒体类型、是否带外链
- 打开 Explore 时记下趋势名、帖子量、领域
- 在帖子分析页上点"读取本页分析数据"，从页面文字里读主页访问、新增关注、链接点击等（**实验功能**，依赖界面文字）
- 记录存在本浏览器的 localStorage（最多 2500 条，超出丢最旧的），点导出时生成 CSV 下载

**不做**：
- 不发任何额外请求，不改页面的请求
- 不自动滚动、不自动翻页、不自动点击——你看到了什么就记什么
- 不上传任何数据；没有服务器
- 不做反检测、不伪装

## 安装

1. 浏览器装 [Tampermonkey](https://www.tampermonkey.net/) 或 [Violentmonkey](https://violentmonkey.github.io/)
2. 新建脚本，把 [`cheatx-exporter.user.js`](cheatx-exporter.user.js) 全文粘进去保存（或在扩展里"从 URL 安装"指向你仓库里这个文件的 raw 地址）
3. 打开 x.com，左下角出现 `cheat-on-x · N 帖` 小面板
4. 点"设置我的 handle"，填你的 X 用户名（不带 @）

## 日常用法

| 要做什么 | 在 x.com 上 | 然后点 |
|---|---|---|
| 复盘到期的帖子 | 打开**自己的主页**往下滚，滚过要复盘的那几条；想要回复就**点进那条帖子**、把回复区滚一遍 | 导出：我的帖子 + 回复/引用 |
| 补主页访问 / 新增关注 | 帖子 → 查看帖子分析 | 读取本页分析数据（实验）→ 再导出 |
| 导入对标账号 | 打开对标账号主页往下滚 15-30 条 | 导出：全部已记录帖子 |
| 抓热点 | 打开 Explore / 趋势页 | 导出：趋势 |

导出的文件放进你 X 内容项目的 `imports/` 目录（已在 .gitignore 里），然后在 Claude Code 里说：

```
复盘到期的 imports/cheatx-mine-20261114-2130.csv
```

## 导出的 CSV 列

`post_id, url, author, created_at, captured_at, form, text, impressions, likes, reposts, quotes, replies, bookmarks, engagements, profile_visits, new_follows, link_clicks, detail_expands, media_views, shares, has_link, media, lang, in_reply_to_id, in_reply_to_user, conversation_id, quoted_id, is_note_tweet, is_article, source`

- `captured_at` 是你浏览到它的时间——复盘用它判断"距发布多少小时"
- 同一条帖子多次浏览：保留最新的数字；分析页读到的字段不会被后来的时间线数据覆盖成空

## 保盲提醒

导出文件里会有**所有**你浏览过的帖子，包括刚发、还没到复盘时间的那条。没关系——`x-csv-import` 只会把**到期**帖子的数字写进报告和对话；没到期的不会被打印出来。只是别自己打开 CSV 去看那一行。

## 隐私

- 记录只在这个浏览器里；"清空记录"会删掉
- CSV 里有别人的回复和 handle，所以 `imports/` 不入 git；复盘报告 `posts/<id>/report.md` 只保留回复正文和赞数，**不写回复者的 handle**

## 坏了怎么办

X 改了数据结构时，最可能的症状是"面板计数不涨"或"某一列全空"。

- 打开浏览器控制台看有没有 `[cheat-on-x]` 报错
- 脚本按对象形状找帖子（`__typename: "Tweet"` 或带 `rest_id` + `legacy.full_text` 的对象），不依赖接口名，一般比 DOM 抓取稳
- 实在不行：复盘时手动粘贴数据，`cheatx-retro` 照常工作

## 开发

```bash
node --check userscripts/cheatx-exporter.user.js
node --test userscripts/test/exporter.test.js
```

测试用的是按 X GraphQL 形状手写的合成数据；最后一个测试把脚本导出的 CSV 交给 Python 导入器，检查两边的列契约。**真实 x.com 页面需要你在自己浏览器里装上试一次**——形状如果和合成数据不一致，以真实页面为准修 `parseTweet`。
