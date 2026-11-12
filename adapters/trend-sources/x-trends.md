# Trend source: x-trends（X 站内趋势）

被 `cheatx-trends`、`cheatx-seed`（Mode C / `--batch`）调用。输出符合 [candidate-schema.md](../../shared-references/candidate-schema.md)。

## 两条取法

### A. 油猴脚本导出（默认，免费）

1. 在 x.com 打开 Explore → 趋势 / For you（个性化趋势就是 X 认为"你的圈子"在聊的东西，对 NF 最有用）
2. 左下角面板点"导出：趋势" → 得到 `cheatx-trends-YYYYMMDD-HHMM.csv`，放进 `imports/`
3. 转成候选：

```bash
python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py trends imports/cheatx-trends-xxxx.csv
```

每行一个候选 JSON：`source: "trend:x-trends"`，`expires_at` = 抓取时间 + 24h（热点过期快）。

### B. X API（可选，按量计费）

```bash
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py trends --woeid 1            # 预演，看费用
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py trends --woeid 1 --yes      # 执行
```

`--woeid`：1 = 全球，23424977 = 美国，其他地区查 X API 文档。API 版是**地区**趋势，不是个性化趋势；个性化趋势需要用户授权，本 adapter 没有实现。

## 字段映射

| candidate 字段 | 来源 |
|---|---|
| `title` | `（X 趋势）<趋势名>` |
| `snapshot_text` | 趋势名 · 帖子量 · 领域标签 |
| `url` | `https://x.com/search?q=<趋势名>` |
| `form_hint` | 不自动填——由 cheatx-trends 粗打分时判断（热点通常适合 `quote` 或 `single`） |
| `expires_at` | 抓取 + 24h |

`snapshot_text` 只有趋势名和标签，信息量少。cheatx-trends 打分前应该问用户"这个趋势你有什么一手的东西可说"——没有一手角度的热点，FT 和 NF 通常都低。

## 失败降级

没有导出文件 / 没配 token / API 失败 → 返回空，回落到 `trendradar-mcp`、`aihot` 或 manual-paste。不抛异常。

## 稳定性

- 油猴导出：依赖 X 的趋势数据形状（`TimelineTrend` 对象），X 改版可能失效——面板上"趋势"计数不涨就说明坏了
- API：稳定，但要钱
