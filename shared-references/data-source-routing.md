# Data Source Routing — 热点 / 素材工具的触发与路由

被 `cheatx-seed` / `cheatx-trends` 引用。规定**何时**调热点工具、**调哪个**、**不调时怎么办**。

---

## 核心哲学

> 热点工具是**素材库**，不是主菜单。
>
> - 用户在**内省**（讲自己的经历、一手经验）→ **不调**，外部信息是噪音
> - 用户在**找素材**（没想法 / 要批量 / 显式抓热点）→ **调**
> - 用户讲的本身是时事 → 不主动调，问一句要不要看看 X 上现在怎么讨论

在 X 上 FT（关注转化）和 NF（圈层契合）的最好来源是你自己的一手经验。热点帮你蹭到流量，但蹭多了会稀释"你是谁"——所以默认不调。

---

## 触发矩阵（cheatx-seed）

| 场景 | 默认调？ | 条件 |
|---|---|---|
| Mode A：用户给了具体经历 / 话题 | ❌ | 仅当话题是时事（专有名词 + 时间词）且用户同意 |
| Mode B：方向模糊，在想"为什么" | ❌ 永不 | 内省阶段 |
| Mode C：完全没想法 | ✅ | |
| `--batch N` | ✅ | 批量要有 anchor |
| `/cheatx-trends` 显式 | ✅ | |
| `/cheatx-recommend` | ❌ | 候选池 > 3 天没更新 → 提示先抓 |

时事判定交给 Claude：专有名词（人名 / 产品名 / 事件名）、时间词（"今天"、"刚刚"）= 强信号；只有通用名词 + 个人经历词 = 反信号。

---

## 数据源

| Adapter | 适合 | 成本 |
|---|---|---|
| [`x-trends`](../adapters/trend-sources/x-trends.md) | X 站内正在讨论什么（Explore 趋势） | 油猴导出：免费；API：按量计费 |
| [`aihot`](../adapters/trend-sources/aihot.md) | AI 行业 / AI 工具账号 | 见 adapter |
| [`trendradar-mcp`](../adapters/trend-sources/trendradar-mcp.md) | 中文全网热点（适合面向中文读者的账号） | MCP 调用 |
| `manual-paste` | 永远的兜底：用户粘标题 / 链接 / 自己收藏的帖子 | 免费 |

### 按账号定位路由

| 账号定位 | 主调 | 备调 |
|---|---|---|
| AI / 科技 / 开发者 | x-trends + aihot | trendradar-mcp（中文圈） |
| 中文泛话题（职场 / 生活 / 观点） | trendradar-mcp + x-trends | — |
| 英文泛话题 | x-trends | — |
| 垂直小圈子 | manual-paste（圈内人收藏夹最准） | x-trends（个性化趋势） |

`.cheatx-state.json` 的 `enabled_trend_sources` 是显式开关，数组里有的才调；空数组 → 只走 manual-paste。单次覆盖：`/cheatx-trends — sources: aihot`。

---

## 失败降级

```
主调 → 失败（无导出文件 / 无 token / MCP 没装 / 超时）
  → 备调 → 失败
    → manual-paste："今天刷到什么值得发的？粘几条标题或链接给我"
```

所有失败都**不抛异常**——cheatx-seed 永远能跑。

---

## 成本意识

- x-trends 走 API 时每次调用都花钱：调用前打印预估费用；同一会话最多 1 次
- 油猴导出：用户在浏览器里点一下导出，零 API 成本——推荐默认
- 同一会话不要反复调同一个源；用户连说"再来一批"第三次时，建议换角度

---

## 与 candidates.md 的关系

```
[trend source] → items → 去重（candidates.md / predictions / trends-history）→ 粗打分 → 写入 candidates.md
```

先入池、再从池里选——可追溯、可被 `cheatx-recommend` 复用。

---

## 扩展

新增一个源：写 `adapters/trend-sources/<name>.md`，在本文件"数据源"表加一行。不要把源名硬编码进 cheatx-seed。
