# X 版移除清单

cheat-on-x 从 [cheat-on-content](https://github.com/XBuilderLAB/cheat-on-content)（`d88d004`）派生。下面这些在 X 版里**移除**，原因是它们只服务视频 / 国内平台。**上游仓库里它们都还在**，需要时去上游取；本仓库的 git 历史里也能找回（`git show d88d004:<path>`）。

| 移除项 | 原因 | 去向 |
|---|---|---|
| `adapters/perf-data/douyin-session/` | 抖音视频后台数据 | 上游同路径 |
| `adapters/perf-data/xhs-explore/` | 小红书笔记数据 | 上游同路径 |
| `adapters/perf-data/bilibili-stat/` | B 站视频数据 | 上游同路径 |
| `adapters/perf-data/wechat-channels/` | 视频号后台数据 | 上游同路径 |
| `adapters/perf-data/linkedin-session/` | LinkedIn 帖子分析（Playwright 登录态抓取）。X 版不走登录态自动抓取，改用油猴脚本 + CSV 导入 | 上游同路径 |
| `adapters/script-extraction/whisper/` | 视频转文字。X 帖子本身是文字 | 上游同路径 |
| `adapters/trend-sources/weibo-hot.md`、`zhihu-hot.md` | 国内平台热搜。X 版用 `x-trends`，保留了 `aihot`、`trendradar-mcp` | 上游同路径 |
| `starter-rubrics/*`（opinion-video、long-essay、podcast、short-text 等 7 份） | 视频 / 文章 rubric。X 版换成 `x-post-zero.md`、`x-longform-zero.md` | 上游同路径 |
| `migrations/1.0-to-1.1.md` … `1.3-to-1.4.md` | 上游 state 的升级链。X 版 schema 从 `x1.0` 重新起步 | 上游同路径 |
| `.github/workflows/star-history.yml`、`tools/gen-star-history.py`、`tools/xkcd-font.css`、`docs/star-history.svg` | 上游仓库的 star 曲线自动刷新 | 上游同路径 |
| `docs/guancha-no1.svg` | 上游的观猹热榜徽章，属于上游项目的荣誉 | 上游同路径 |

## 改名对照

| 上游 | X 版 |
|---|---|
| `cheat-on-content`（根 skill） | `cheat-on-x` |
| `cheat-*` 子 skill | `cheatx-*` |
| `cheat-shoot`（拍了） | `cheatx-queue`（定稿入队） |
| `.cheat-state.json` / `.cheat-cache/` / `.cheat-hooks/` / `.cheat-secrets.json` | `.cheatx-state.json` / `.cheatx-cache/` / `.cheatx-hooks/` / `.cheatx-secrets.json` |
| `scripts/` / `videos/<id>/script.md` | `drafts/` / `posts/<id>/final.md` |
| `script_patterns.md` | `post_patterns.md` |
| `CHEAT_BYPASS_IMMUTABILITY` | `CHEATX_BYPASS_IMMUTABILITY` |
