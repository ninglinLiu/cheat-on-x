---
name: cheatx-persona
description: 从复盘段的回复和引用里聚类出你在 X 上的真实读者画像（谁在回复、为什么来、怎么说话、谁不是你的读者），写 audience.md。没有复盘数据但有对标时，先 seed 一份未验证画像。audience.md 含实际信号，盲打 sub-agent 读不到它——画像只影响写什么，不影响怎么打分。触发词："受众画像"/"我的读者是谁"/"更新 persona"/"build persona"。
argument-hint: "[— seed-from-benchmark] [— rebuild]"
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /cheatx-persona — 读者画像

## 定位

persona 和 rubric 是复盘数据的两个**平行**派生物：

```
复盘数据（回复 + 引用 + 收藏/关注信号）
   ├──→ rubric（cheatx-bump）   —— 这条会不会好 → 喂 cheatx-predict
   └──→ persona（cheatx-persona）—— 谁会停下来、回复、关注 → 喂 cheatx-seed
```

persona **不进打分公式**。

## ⚠️ 污染隔离

`audience.md` 由回复派生 = 含已发布帖子的实际信号：
- 在 `cheatx-score-blind` 的禁读清单里（`blocked_audience`）
- 只给 `cheatx-seed` 当创作视角

## Constants

- **MIN_RETROS_FOR_DATA_GROUNDED = 5**（X 单条回复少，门槛比上游高）
- **MIN_REPLIES_PER_TRAIT = 3**——一条"验证特征"至少 3 条回复证据，否则降到"假设特征"
- **SEED_FROM_BENCHMARK = auto**

## Inputs

| 来源 | 用途 |
|---|---|
| `predictions/*.md` 的 `## 复盘`（回复与引用一节） | 主数据：聚类后的回复 |
| `posts/*/report.md` | 回复 / 引用原文（带赞数，不带 handle） |
| `samples/<对标>/`、`benchmark.md` | 冷启动 seed |
| `rubric-memo.md` | Phase 3 交叉检验（哪些话题实际表现好） |
| `audience.md`（已有） | Phase 5 diff |

## Workflow

### Phase 0：收集

只读复盘段和 report.md 的回复 / 引用部分（这是 channel A，本来就看结果）。统计有回复的复盘条数 `N_retros`、回复总数 `N_replies`、引用总数 `N_quotes`。

### Phase 1：数据量 → confidence

| 情况 | confidence | 行为 |
|---|---|---|
| `N_retros = 0`、无对标 | 🔴 | 不硬造："先复盘几条，或导入对标"，退出 |
| `N_retros = 0`、有对标 | 🟠 seed | 从对标样本的回复（如有）和话题 seed 一份**愿景画像**，全文标"未验证" |
| 1-4 | 🟡 | 能写，但特征大多进"假设" |
| 5-14 | 🟢 | 正常 |
| ≥ 15 | 🔵 | 可以按话题分层 |

### Phase 2：聚类（四个维度）

1. **身份**：回复里自报的身份（"作为独立开发者……"、"我们团队也……"）——同行 / 潜在用户 / 学生 / 路人？
2. **来意**：补充 / 求资源 / 共鸣 / 反对 / @朋友 / 问"你是做什么的"——各占比
3. **边界**：哪些观点稳定引来反对；哪些话题吸引来的是"路人"（回复离题、不关注）
4. **语言**：怎么说话——术语密度、中英混用、玩梗、复用你的句式

纪律：
- 每条验证特征带证据：回复摘录 + 出处（哪条预测的复盘）+ 条数
- 不写任何具体的人的 handle
- 发现"你以为的读者 ≠ 实际回复的人" → 写进"反画像"

### Phase 3：persona × rubric 交叉检验

persona 说"读者爱 X 类话题"，`rubric-memo.md` 里 X 类帖子的实际倍数真的高吗？不一致就写出来，不强行调和——矛盾本身是信号（persona 可能在自欺，也可能 rubric 漏了维度）。

### Phase 4：写 audience.md

覆盖式重建（模板 [templates/audience.template.md](../../templates/audience.template.md)）：
- header：版本 +1、`Last rebuilt`、数据基础、confidence
- 底部"版本历史"追加一行：`vN — 基于 M 条复盘 / K 条回复，主要变化：……`

不走 Memo、不走跨模型审核——画像写错了重跑就好。

### Phase 5：报告

```
✅ audience.md v2（🟢，基于 12 条复盘 / 148 条回复 / 9 条引用）

核心：做 AI 工具的独立开发者和小团队技术负责人，来找能直接用的做法
变化：
  + 新验证：「求模板」类回复占 27%（SV 高的帖子尤其多）
  − 推翻：以为学生是主要读者——回复里自报学生身份的只有 2 条
⚠️ 交叉检验：画像说"读者爱行业观点"，但观点类帖子实际 / 中枢平均 0.6×——待下次复盘澄清
```

## Key Rules

1. 不进打分
2. 每条特征有证据，否则进"假设"
3. 必须写反画像
4. 不写 handle

## Refusals

- 「按我想要的读者写一份画像」 → 那是愿景，不是画像；可以写进"假设特征"并标"愿景"
- 「把画像给打分 sub-agent 参考」 → 拒绝，会把结果信号带进盲打

## Known limitations

- 回复的人 ≠ 读的人：大部分读者只看不回。画像偏向"会说话的那部分读者"
- X 上回复区会被大号、机器人、引流号污染——聚类时剔除明显离题 / 刷屏的
