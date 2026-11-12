---
name: cheatx-trends
description: 从启用的热点源抓今天的素材（X 趋势：油猴导出或 X API；aihot；trendradar-mcp；手动粘贴）→ 去重 → 粗打分 → 问用户"这个你有没有一手角度" → 写入 candidates.md（带 24 小时过期）。触发词："抓 X 热点"/"抓热点"/"fetch trends"/"今天有什么可发的"/"trending"。
argument-hint: "[— sources: <comma-separated>] [— max-per: 20]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheatx-trends — 热点入池

读各 trend source → normalize 成候选 → 去重 → 粗打分 → 用户挑 → 写 candidates.md。

## Constants

- **TREND_SOURCES** = `state.enabled_trend_sources`（默认 `["manual-paste"]`）
- **MAX_PER_SOURCE = 20**
- **DEFAULT_EXPIRY_HOURS = 24**
- **MIN_COMPOSITE_TO_SUGGEST = 6.0**——低于这个分不推荐入池（仍记进 trends-history 防止下次重复推）

## Workflow

### Phase 0：启用了哪些源

`— sources:` 覆盖 > `state.enabled_trend_sources`。为空 → 引导：

```
还没有启用热点源。可用的（见 adapters/trend-sources/）：
- x-trends：在 x.com 打开 Explore → 油猴面板"导出：趋势"（免费）；或 X API（付费）
- aihot：AI 圈精选（AI / 科技账号）
- trendradar-mcp：中文全网热点（需配 MCP）
- manual-paste：你粘标题 / 链接（永远能用）
临时用：/cheatx-trends — sources: x-trends,manual-paste
永久启用：改 .cheatx-state.json 的 enabled_trend_sources
```

### Phase 1：逐个源取数

| 源 | 怎么做 |
|---|---|
| `x-trends`（油猴） | 让用户导出趋势 CSV 到 imports/，然后 `python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py trends imports/<file>.csv` → 每行一个候选 JSON |
| `x-trends`（API） | `xapi.py trends --woeid <n>` 先预演给费用，用户同意加 `--yes` |
| `aihot` | 见 [aihot.md](../../adapters/trend-sources/aihot.md) |
| `trendradar-mcp` | 见 [trendradar-mcp.md](../../adapters/trend-sources/trendradar-mcp.md) |
| `manual-paste` | "粘你今天刷到的值得发的东西（标题 / 链接，一行一条）"→ 链接用 WebFetch 拓展摘要（X 帖子链接 WebFetch 通常拿不到内容，请用户直接粘正文） |

单个源失败 → 跳过并说明，不抛异常：

```
✅ x-trends：32 条
✅ aihot：18 条
⚠️ trendradar-mcp：跳过（MCP 未配置）
```

### Phase 2：normalize

全部转成 [candidate-schema.md](../../shared-references/candidate-schema.md)；X 趋势和热点新闻设 `expires_at` = 抓取 + 24h。

### Phase 3：去重

按 candidate-schema 的去重规则：candidates.md 已有 / 已发过 / 30 天内被拒过 / 已过期 → 跳过。

### Phase 4：粗打分

候选只有一句话 + 摘要，不是草稿——这里的打分是**粗筛**，不走盲打 sub-agent（素材本身不含你的结果数据，没有污染问题）：
- 按 rubric 维度给粗分（HK 按"能不能写出一个好的第一行"估；NF 按和你账号定位的距离估）
- `form_hint`：热点通常 `quote`（引用最核心的原帖加一手判断）或 `single`
- 记 `TM`（时效）候选维度分

### Phase 5：用户挑

按 composite 排，展示 top 10（≥ `MIN_COMPOSITE_TO_SUGGEST`）：

```
| # | 素材 | 来源 | 建议形态 | composite | NF | 过期 |
|---|---|---|---|---|---|---|

哪些进候选池？（"1,3,5" / "全部" / "都不要"）
⚠️ 对每条想一下：这件事你有没有一手的东西可说？没有的话，NF 和 FT 都会低——蹭到流量也留不住人。
```

### Phase 6：落盘

- 选中的 → candidates.md（tier 按 composite：≥ 7.5 tier1，6-7.5 tier2）
- 全部（含未选中的）→ `.cheatx-cache/trends-history.jsonl` 追加一行，未选中的记 `rejected_at`

### Phase 7：state

`last_trends_run_at`、`last_trends_added_count`。

## Key Rules

1. 失败降级，不抛异常
2. 热点必须带过期时间
3. 粗打分不冒充预测——`predicted_bucket` 只是粗估
4. 同一会话同一个付费源最多调 1 次

## Refusals

- 「把今天的热搜全部加进候选池」 → 拒绝，先筛
- 「热点自动帮我写好发出去」 → 拒绝。写草稿走 /cheatx-seed，发布是你的动作

## Integration

- 下游：`/cheatx-recommend`、`/cheatx-seed`（Mode C）
- 路由规则：[data-source-routing.md](../../shared-references/data-source-routing.md)
