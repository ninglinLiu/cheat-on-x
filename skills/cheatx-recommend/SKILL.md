---
name: cheatx-recommend
description: 从 candidates.md 挑今天发什么：按队列颜色、"1 稳 + 1 实验"、话题不连发、发帖间隔，给出推荐 + 每条的维度分 + 锚点 + 建议发布时间。候选池为空时给引导而不是报错。触发词："推荐今天发什么"/"下一条发什么"/"next post"/"挑一个选题"/"recommend"。
argument-hint: "[— top: N] [— filter: tier1|all|safe|risky]"
allowed-tools: Read, Glob, Grep
---

# /cheatx-recommend — 今天发什么

读 candidates.md → 过滤 → 按队列颜色调整策略 → 1 稳 + 1 实验 → 建议发布时间。

## Constants

- **TOP_N = 3**（X 节奏快，给多了没人看）
- **STRATEGY = stable+experimental**（见 [cadence-protocol.md](../../shared-references/cadence-protocol.md)）
- **REQUIRE_SCORED = true**——没打过分的候选不推
- **CATEGORY_LOOKBACK** = max(3, `target_posts_per_day` × 2) 条主帖内不推同类
- **MIN_SPACING_MINUTES = 120**

## Workflow

### Phase 0：候选池在不在

`candidates.md` 不存在或为空 → **不报错**，给引导：

```
你还没有候选池——很正常。三种建法：

1. 🌱 /cheatx-seed（推荐）：告诉我一件你最近经历 / 观察到的事，我帮你挖角度、写草稿
2. 🔥 /cheatx-trends：在 x.com 打开 Explore 用油猴脚本导出趋势，或接 aihot / trendradar，
   我粗打分后放进候选池
3. ✍️ 手写 candidates.md：一行一个 `### 标题`，下次我自动补分
```

### Phase 1：解析

每个 `### [tier] 标题` 是一条候选，读字段（见 [candidate-schema.md](../../shared-references/candidate-schema.md)）。

### Phase 2：过滤

- `tier` 是 `skip` / `done` → 去掉
- `expires_at` 已过 → 去掉（热点过期了）
- 已有同 id 的预测文件 → 去掉
- 没 composite → 不推（`REQUIRE_SCORED`），在末尾列"有 N 条没打分，要我先粗打一遍吗？"
- 同 `category` 在最近 `CATEGORY_LOOKBACK` 条主帖里出现 ≥ 2 次 → 降级到"备选"
- `filter: safe` → 去掉 `risky` 和 NR ≥ 3 的

### Phase 2.5：队列颜色覆盖（最高优先级）

| 颜色 | 策略 |
|---|---|
| 🔴 | 只推稳分 top 1——"今天能发出来就行" |
| 🟠 | 1 稳 + 1 实验，先写稳的 |
| 🟢 | 标准 1 + 1（+ 1 备选） |
| 🔵 | 不推新的："队列已经够发 N 天，先发存货"——列出队列里该先发的那条 |

### Phase 3：选

**稳**：composite 最高、NR ≤ 1、和最近主帖不同类；同分时优先 `form_hint` 是你基线最稳的形态。

**实验**：能验证 `rubric-memo.md` 里某个"待验证假设"或 `post_patterns.md` 里某个单样本 pattern 的候选。说清楚它测什么："这条是 thread，用来测 thread 相对 single 的倍数（你目前只有 2 条 thread 样本）"。composite 不一定高。

**锚点**：每条推荐找 1-2 条 composite 接近、同形态的已复盘帖子，写它们的实际倍数（相对当时基线）。

**发布时间**：
- 距上一条主帖 ≥ `MIN_SPACING_MINUTES`
- 如果 `rubric-memo.md` 里已有时段相关的观察（如"晚间表现更好"，≥ 3 条样本），按它建议；没有就不编，只保证间隔
- 热点候选：越早越好，标"尽快"

### Phase 4：输出

```
📦 队列 0 条 🔴 · 今天 1 / 3 · 距上一条 2.5 小时

🎯 今天发：

1. 【稳】我用 AI 写作半年后删掉的 7 个提示词（thread）
   composite 7.6 · HK4 RP3 SV5 RS3 DW4 FT4 NF5 NR1
   锚点：「提示词模板」7.0 → 2.1× 基线；「周报自动化」7.4 → 0.6×（NF 只有 3）
   理由：SV 主导 + 核心话题，你最稳的路线
   建议时间：现在之后任意时间（间隔已够）

2. 【实验】（X 趋势）某开源模型发布 → 引用官方帖加一手测试结论（quote）
   composite 6.4 · TM 候选 5
   测什么：热点 quote 的倍数，以及 TM 维度有没有独立预测力
   ⏳ 24 小时内过期——尽快

下一步："帮我写第 1 条"（→ /cheatx-seed）或你自己写好后 "快押 drafts/…"
```

## Key Rules

1. 永远展示维度分 + 至少一个锚点（锚点不够就写"锚点 N/A，校准样本不足"）
2. 不推没打分的
3. 实验必须说清楚测什么
4. 不编时段规律——没有数据支撑就只保证间隔

## Refusals

- 「直接挑 composite 最高的，不用解释」 → 拒绝，永远带维度和锚点
- 「凭感觉推一个」 → 拒绝，先打分
- 「全推实验的」 → 最多一半，冷启动期实验失败率高

## Integration

- 上游：`/cheatx-trends`、`/cheatx-seed` 写入 candidates.md
- 下游：`/cheatx-seed`（写草稿）→ `/cheatx-predict`
- 读 `state.queue`、`recent_publishes`、`rubric-memo.md`（待验证假设，只在主对话里读——它不进打分）
