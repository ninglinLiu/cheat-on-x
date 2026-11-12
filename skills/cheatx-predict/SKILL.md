---
name: cheatx-predict
description: 给一条（或一批）X 帖子草稿写 immutable 盲预测日志——cheat-on-x 校准循环的核心动作。三种模式：完整预测（thread / 长帖 / 重要帖子）、快押（日常短帖，每个组件可一行）、批量（一次给 drafts/ 下多条打分预测）。打分委派给 `cheatx-score-blind` sub-agent，主 Claude review 后落盘；预测段写完由 hook 锁死。被 cheatx-queue 以 v2 模式调用时在原文件追加 `## 预测 v2`。**必须在发布之前跑。**触发词："启动预测"/"快押"/"批量预测"/"start prediction"/"给这条写预测"。
argument-hint: '<draft-path|drafts/> [— mode: full|quick|batch|v2] [— prediction-file: <path>] [— skip-blind]'
allowed-tools: Bash(*), Read, Write, Edit, Glob, Task
---

# /cheatx-predict — 盲预测 + 用户 review

这个工具的核心是 **AI 帮你做判断**：
- Claude 读草稿 → 盲打 8 维分 → 给 bucket + 概率 + 中枢 + 反事实
- 用户 review：回 "ok" 落盘，或指出哪个判断不对
- 落盘后预测段锁死

严格遵守 [blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md)。结构见 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md)。confidence 表见 [state-management.md](../../shared-references/state-management.md)。

## Overview

```
[启动预测 / 快押 / 批量预测]
  ↓
Phase 0   盲度自检（每条）——发出去了就拒绝
Phase 0.5 解析输入 + 选模式（full / quick / batch / v2）
Phase 1   读草稿 + rubric + state → 基线、confidence、协变量
Phase 2   委派 cheatx-score-blind（批量一次最多 10 份）
Phase 2.5 分歧检测：|盲分 − 主估| ≥ 2 → 用户裁定
Phase 3   锚点对比
Phase 4   bucket + 概率 + 中枢 + 次要押注
Phase 5   反事实 + 关键校准假设
Phase 5.5 用户 review（批量时一张总表）
Phase 6   落盘（v1 新文件 / v2 追加）
Phase 7   更新 state
Phase 8   控制台总结
```

## Constants

- **BLIND_CHECK = strict**（lenient 只用于演练）
- **BLIND_SCORING = on**——off 等于 `--skip-blind`
- **DISAGREEMENT_THRESHOLD = 2**
- **MAX_BATCH = 10**——一次 sub-agent 最多打 10 份
- **DEFAULT_MODE**：`thread` / `long` / `article` → `full`；`single` / `quote` / `reply` → `quick`（用户可以覆盖）
- **MIN_ANCHORS = 2**；锚点 composite 邻近范围 ±0.7

## 草稿文件格式（`drafts/<date>_<id>_<short>.md`）

```markdown
---
form: thread            # single | thread | long | article | quote | reply
media: image（对比表截图）  # text | image | video | gif | poll，可加说明
has_link: no
quote_target: n/a       # quote / reply 时填被引用 / 被回复帖子的链接
planned_at: 2026-11-12T21:00+08:00   # 可选
---

1/ 我用 AI 写作半年后，删掉了 7 个提示词。留下的 3 个每天在用。

2/ ……

## 被引用 / 被回复的帖子（上下文，不打分）
（quote / reply 才需要：贴原帖正文）
```

没有 frontmatter → 问用户形态，然后补上（这是发布前信息，不影响盲度）。

## Workflow

### Phase 0：盲度自检（每条都查，最关键）

按 [blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md)：

1. 问一句（批量时一次问完）："这些都还没发吧？"
   - 没发 → 通过
   - 已发 → 这一条转 reconstructed（`_redo.md`，不进校准池）。唯一例外：发出 ≤ 10 分钟且用户确认没看任何计数和回复 → 允许，header 标 `published_before_prediction: true`
2. 扫当前对话：出现过这条帖子的浏览 / 赞 / 回复数字或回复内容 → reconstructed
3. 本会话刚导入过包含这条帖子的 CSV → reconstructed

通过才进 Phase 0.5。

### Phase 0.5：解析输入 + 选模式

| 输入 | 处理 |
|---|---|
| `drafts/<date>_<id>_<short>.md` | 单条 |
| `drafts/`（目录）或多个路径 | 批量：列出所有**还没有对应 predictions/ 文件**的草稿，让用户确认清单 |
| `<id>` 或 `<short>` | glob `drafts/*_<id>_*.md` / `drafts/*<short>*.md` |
| drafts/ 外的文件 | 问"要我复制到 `drafts/<今天>_<id>_<short>.md` 管理吗？"——同意才继续 |
| `— mode: v2 — prediction-file: <path>` | v2 模式（`cheatx-queue` 调用） |

模式自动判定：
- 对应 `predictions/<同名>.md` 已存在且含 `## 预测` 段 → **v2 模式**（必须由 cheatx-queue 触发，或用户明确要求；否则提示"这条已经预测过了，要改稿重判请走 `定稿`"）
- 不存在 → v1；单条按 `DEFAULT_MODE` 选 full / quick；多条 → batch（内部每条仍按形态选 full / quick）

v2 额外：读 `posts/<同名>/final.md`，与预测时的 `Draft Hash` 比较；没变 → "定稿没改，不需要 v2"。

### Phase 1：读入 + 派生

每条：
1. 读草稿全文和 frontmatter → `form` / `media` / `has_link` / `quote_target` / `planned_at`
2. `draft_hash` = sha256(全文)[:12]；`id` 从文件名取
3. 读 `rubric_notes.md`（当前公式、维度）
4. 读 `.cheatx-state.json`：`rubric_version`、`calibration_samples`、`baseline_impressions`、`followers_at_init`、`x_premium`、`recent_publishes`
5. **confidence** ← `calibration_samples`
6. **基线**：`baseline_impressions[form]` → 不足则 `all` → 都没有则 `max(100, 粉丝数 × 0.3)`（粉丝数问用户当前值，记进 header 的 `Followers at Predict`）
7. **协变量**：计划发帖时间（问；不知道写 `unplanned`）、距上一条主帖分钟数（从 `recent_publishes` 估）、Premium、外链、媒体
8. 字数检查：单帖超过 280 加权字符（中文按 2 计）但没开长帖 → 提醒用户"这条发不出去，要拆 thread 还是发长帖？"

### Phase 2：委派 cheatx-score-blind

主 Claude **不在主对话里打分**。Task prompt 只含草稿路径和 rubric 路径（契约见 [cheatx-score-blind](../cheatx-score-blind/SKILL.md)）：

```
Spawn cheatx-score-blind sub-agent.

Input:
  draft_paths:
    - drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md
  rubric_notes_path: rubric_notes.md

Task: 按 rubric_notes 当前公式给上面每份草稿独立打分。返回严格 JSON（见 cheatx-score-blind SKILL.md Phase 2）。
不要读任何其他文件。不要询问用户——你没有用户。
```

- v2 模式传 `posts/<同名>/final.md`
- 批量 > 10 份 → 分多次 Task
- 发送前自检 prompt（不得含数字 + 曝光 / views、handle、predictions 路径）

**主 Claude 同时自己内心估一份分**——只用于 Phase 2.5 的分歧检测，最后连同盲分一起记进 header。

composite 用**盲分**按当前公式算。

`--skip-blind` / `BLIND_SCORING=off`：主 Claude 自己打，state 标 `last_prediction_self_scored: true` + `last_self_scored_at`，cheatx-status 持续提醒。只在 Task tool 不可用时用。

### Phase 2.5：分歧检测

1. JSON 能解析（不能 → 重发，最多 3 次，仍失败 → 停下告诉用户）
2. `self_check.any_contamination_signal` → 告诉用户 sub-agent 报了疑似污染，confidence 降一档
3. `refusal` → 按 cheatx-score-blind 的表处理
4. 每维 `delta = |主估 − 盲分|`；任一维 ≥ 2 → 弹裁定：

```
⚠️ 盲打 sub-agent 和我在这几个维度差得多：

| 草稿 | 维度 | 盲分 | 我的估计 | 差 | sub-agent 理由 |
|---|---|---|---|---|---|
| ai写作清单 | RP | 3 | 5 | 2 | 清单可补充但没留分歧点 |

信谁？ a) sub-agent  b) 我的估计  c) 你直接给分（如 "c RP=4"）
```

- a → 用盲分
- b → 用主估，标 `last_prediction_self_scored: true`，`BlindScored By: main-claude-self`
- c → 该维用用户分，`BlindScored By: mixed`，记 `User Override`

所有维度的 delta（含 0）都写进 `BlindScore Disagreement`。

NF 的盲分 confidence 常为 low（sub-agent 看不到账号定位）——主 Claude 可以结合账号定位给出不同意见，同样走裁定。

### Phase 3：锚点对比

1. Glob `predictions/*.md`，读 header 与复盘段（排除 reconstructed / `_redo` / Integrity warning 的）
2. **优先同形态**，再找 composite ±0.7 的 2-4 条
3. "实际"一栏写**相对当时基线的倍数**
4. 不够 2 条 → 写"锚点 N/A"段，不删段
5. composite 几乎相同但实际倍数差 ≥ 3× 且无外生冲击 → 在文件里标"rubric 可能漏维度"作为观察种子

### Phase 4：bucket + 概率 + 中枢

1. 按 Phase 1 基线换算 5 个倍数桶的曝光区间
2. 选 headline bucket；中枢写成具体曝光数
3. 概率加和 100%；headline 通常 35-55%；confidence 🔴 / 🟠 时更平
4. 次要押注：`full` 写互动率 / 收藏赞比 / 回复数三项；`quick` 至少写互动率或写"省略"

协变量在这里起作用：间隔不足、冷门时段、带外链（如果你的复盘数据显示它有影响）→ 写进推理因素，相应调整分布，**不改维度分**。

### Phase 5：反事实 + 关键校准假设

- 反事实：每个 bucket（可以把 `大爆`/`小爆` 合一段）写"落在这里说明什么"。快押一行
- 关键校准假设：找一条对照（最好同形态的上一条），写"我押本篇 / 对照 = N×"。没有对照写"本次想测：……"

### Phase 5.5：用户 review

**单条**：完整展示

```
我的预测草稿（还没写文件）：

📊 8 维（v0，盲打）
| 维度 | 分 | 理由 |
|---|---|---|
| HK | 4 | 首条「删掉的 7 个提示词」 |
| … | | |
→ composite 7.60（28/7×2 − 0.4）

🎯 命中（420–1,260），中枢 800 · confidence 🟡 偏低
   退步 10% / 持平 30% / **命中 40%** / 小爆 15% / 大爆 5%
   次要：互动率 1–3% · 收藏/赞比 >0.3 · 回复 5–15

🔍 锚点：……
🤔 反事实：……
🎲 校准假设：……

回 "ok" 落盘，或指出哪里不对（"中枢太高" / "RP 给 3"）。
```

**批量**：一张总表，每行一条，用户可以 "全部 ok" 或 "第 2 条中枢改成 500，其余 ok"：

```
| # | 草稿 | 形态 | 模式 | composite | bucket | 中枢 | headline 概率 | 一句话 |
|---|---|---|---|---|---|---|---|---|
```

用户改的字段记进 `User Override`（原值 → 新值 + 理由）。用户只能改值，不能塞新理由让 Claude 代写判断。改完 Claude 连锁更新 composite / 分布。

### Phase 6：落盘

#### 6a v1（新文件）

`predictions/<同 drafts 文件名>.md`，按 [templates/prediction.template.md](../../templates/prediction.template.md)：
- header 所有必填字段（见 prediction-anatomy 组件 1）
- `## 输入快照` → `## 预测 v1` → `## 推理因素` → `## 锚点对比` → `## 反事实场景` → `## 关键校准假设` → 空的 `## 复盘`
- 写前自检：7 个标题齐全、概率 100%、bucket 区间按基线算对

#### 6b v2（追加）

**绝不**用 Write 覆盖。用 Edit 在 `## 复盘` 之前插入：

```markdown
## 预测 v2（replaces v1; basis=pre_publish_v2）

**Diff vs v1**: 定稿相对草稿改动 N%，主要变化：……
**Final Hash**: sha256:<12 位>

[与 v1 同结构的组件 2-7]

---

## 复盘
```

v1 一个字不动。复盘时用最后一个 `## 预测 vN`。

### Phase 7：更新 state

- 流程开始时写 `in_progress_session = {"type": "prediction" | "batch_prediction", "files": [...], "started_at", "rubric_version"}`，落盘完成后清回 null
- `last_prediction_self_scored` / `last_self_scored_at`：走了 sub-agent → false / null；`--skip-blind` 或裁定选 b → true / now

### Phase 8：总结

```
✅ 预测落盘：predictions/2026-11-12_a3f2c1d4e5b6_ai写作清单.md
   命中（中枢 800）· confidence 🟡

⚠️ 预测段已锁。发出去之后别把这条的浏览数 / 回复贴给我——
   不小心看到了也告诉我，我在复盘段补一个 integrity warning。

下一步：
- 发之前 → "定稿 drafts/2026-11-12_…"（定稿和草稿差 ≥30% 会追加 v2）
- 发完 → "已发 https://x.com/…/status/…"
- 48 小时后 → 导出 CSV，"复盘到期的 imports/…"
```

## Key Rules

1. **先预测再发**。发出去的帖子默认不能写预测
2. 维度分是整数
3. 概率加和 100%
4. 必须留空的 `## 复盘` 段——hook 靠它找预测段的边界
5. 讨论在落盘之前完成；落盘后预测段锁死
6. id 是草稿首次落盘内容的 hash，不是时间戳
7. 批量 ≠ 偷工：每条都有自己的文件、自己的 7 个标题

## Refusals

- 「我已经看到这条有 2 万浏览了，你假装没看到给我预测」 → 拒绝，转 reconstructed
- 「先发出去看看头一个小时，再补预测」 → 拒绝，原则 #1
- 「预测段先写一版，数据出来再调」 → 拒绝
- 「改稿了，直接覆盖原预测，不要 v2」 → 拒绝。v1 是档案
- 「快押就别写反事实了」 → 拒绝省标题；可以一行
- 「只写 bucket 不写概率」 → 拒绝
- 「sub-agent 太慢你直接打」 → 只接受显式 `--skip-blind`，并留下 state 标记
- 「批量里有几条已经发了，一起预测了吧」 → 那几条转 reconstructed，其余照常

## Integration

- 前置：`/cheatx-init` 完成，`rubric_notes.md` 存在
- 上游可选：`/cheatx-score` 反复试改稿
- 下游：`/cheatx-queue` → 发布 → `/cheatx-publish` → `/cheatx-retro` → `/cheatx-bump`
- hook：`prediction-immutability.sh` 必须装在项目 `.claude/settings.json`，否则 immutability 只靠自律（cheatx-status 会提醒）
