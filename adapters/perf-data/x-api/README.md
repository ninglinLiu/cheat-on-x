# Adapter: x-api（可选，X API v2，按量计费）

默认路线是[油猴脚本 + CSV 导入](../x-csv-import/README.md)，免费。x-api 是给这些情况准备的：
- 不想每次手动在浏览器里导出
- 要批量拉对标账号历史
- 需要 `non_public_metrics`（主页点击、链接点击）又不想读分析页

它只是一个**取数器**：从 API 拉回数据 → 写成和油猴脚本完全相同列的 CSV（`.cheatx-cache/x-api/`）→ 交给 x-csv-import 生成 report.md。所以两条路线的复盘报告一模一样。

只用 Python 标准库。

## 费用

X API 自 2026 年起默认按量计费，按返回的资源个数收费。xapi.py 里的估价单价（`PRICE_USD`）来自第三方汇总：

| 资源 | 估价单价 |
|---|---|
| 每条帖子（单条查询 / 搜索 / 时间线 / 引用列表） | $0.005 |
| 每个用户（用户名查询） | $0.010 |
| 趋势 | 未知 |

**以 [docs.x.com](https://docs.x.com) 的定价页为准**，变了就改 `PRICE_USD`。

量级参考：单条复盘（帖子本身 + 20 条回复）≈ 21 条帖子读取 ≈ $0.1；拉对标账号 30 条 ≈ $0.16。

## 安全阀：默认只预演

所有会联网的命令，不加 `--yes` 就只打印"计划调用 + 预估上限"，**不发任何请求**（退出码 5）。`cheatx-retro` 等 skill 会先跑一遍预演，把费用给你看，你确认后再加 `--yes`。

## 配置 token

1. 在 [developer.x.com](https://developer.x.com) 建项目和 App，拿 Bearer Token
2. 二选一：
   - 环境变量 `X_BEARER_TOKEN=...`
   - 项目根 `.cheatx-secrets.json`（已在 .gitignore）：`{"x_bearer_token": "..."}`
3. 可选：OAuth 2.0 用户授权 token（`x_user_access_token` / `X_USER_ACCESS_TOKEN`），配合 `--user-context` 取 `non_public_metrics`——**只对你本人、30 天内的帖子有效**

token 永远不写进 `.cheatx-state.json`。

## 命令

```bash
XAPI=<cheat-on-x>/adapters/perf-data/x-api/xapi.py

python $XAPI estimate                                   # 看估价单价
python $XAPI text 1988765432109876543 --yes             # 只取正文（发布一致性检查；不请求指标字段）
python $XAPI post https://x.com/me/status/1988… --out posts/<id>/ --replies 20 --yes
python $XAPI due --project . --replies 20 --yes         # 所有到期的待复盘
python $XAPI history someone --limit 30 --samples-dir samples/someone --yes
python $XAPI history me --limit 50 --project . --yes    # 自己的历史；--project 跳过还没复盘的帖子
python $XAPI trends --woeid 1 --yes                     # 1 = 全球
```

## 限制

- 回复靠 `search/recent` 按 `conversation_id` 搜，**只覆盖最近 7 天**——T+48h 复盘没问题，晚太久就搜不到了
- 新增关注数 API 不提供，需要的话用油猴脚本读分析页或手动粘
- 429 限流：直接报重置时间并退出，**不自动重试**
- 401/403：token 无效或你的套餐不含该端点

## 退出码

`0` 成功 · `1` 鉴权问题 · `2` 输入有误 / 没数据 · `3` 网络或 API 错误 · `4` 限流 · `5` 只预演未执行

## 测试

```bash
cd adapters/perf-data/x-api
python -m unittest test_xapi.py
```

测试用假的 opener 代替网络，不会产生任何费用。**真实 API 响应没有在本仓库里验证过**——第一次用时先拿一条自己的帖子跑 `post --yes`，对照 x.com 上的数字。
