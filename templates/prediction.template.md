# [短名] — 预测日志

> 本模板由 `/cheatx-predict` 填充。所有预测同一结构（7 个组件 + 复盘段）；`quick` 模式每个组件可只写一行，但标题一个不少。
> 规范见 cheat-on-x 的 `shared-references/prediction-anatomy.md`。

**Post ID**: `<12 位 hash>`  ← 草稿首次落盘内容 sha256 前 12
**Short**: `<短名>`
**Form**: `single` | `thread (N)` | `long` | `article` | `quote` | `reply`
**Media**: `text` | `image` | `video` | `gif` | `poll`
**Has Link**: `yes` | `no`
**Reply/Quote Target**: `@handle（粉丝量级）` | `n/a`
**Rubric Version**: `<v0/v1/...>`
**预测时间**: `<ISO 8601 本地时区>`
**Planned Post Time**: `<ISO 8601>`（星期几 + 时段）| `unplanned`
**Draft Path**: `drafts/<date>_<id>_<short>.md`
**Draft Hash**: `sha256:<12 位>`
**Text Length**: `<字数>`（thread 加 `/ N 条`）
**Followers at Predict**: `<整数>`
**Premium**: `none` | `basic` | `premium` | `premium_plus`
**Baseline**: `<form>=<值>` | `all=<值>` | `cold-start guess=<值>`（写清用的哪一级）
**Calibration Samples (at predict time)**: `<N>`
**Confidence**: `<emoji + 标签>`
**Prediction Mode**: `full` | `quick`
**Prediction Basis**: `pre_publish` | `pre_publish_v2`
**Scored By**: `claude` | `claude+user_override`
**BlindScored By**: `subagent-v1` | `main-claude-self` | `mixed`
**BlindScore Disagreement**: `<inline JSON，每维一条>`
**User Override**: `none` | `<字段: claude=X → user=Y（理由）>`
**预测时数据状态**: **blind**（这条帖子尚未发布）

---

## 输入快照

**分数 (vN)**: `HK? / RP? / SV? / RS? / DW? / FT? / NF? / NR?` → composite=**`<X.XX>`**
**候选维度（不进公式）**: `TM?`

**用户改写要点 vs Claude 草稿**:
- [没有草稿对照就写"用户原创稿，无 Claude 草稿对照"]

---

## 预测 v1

> ⚠️ 本段 immutable——`prediction-immutability` hook 会拦截对本段的修改。要重做请建 `<本文件名>_redo.md`。

**Bucket**: `<退步|持平|命中|小爆|大爆>`（`<下限>–<上限>` 曝光）
**中枢**: `<曝光数>`

**概率分布**:
- `退步`（< 0.3× = `<值>`）→ X%
- `持平`（0.3–1×）→ X%
- `命中`（1–3×）→ X%
- `小爆`（3–10×）→ X%
- `大爆`（> 10×）→ X%

> 加起来 100%。confidence 低时分布应该更平。

**次要押注**:
- 互动率：`<1%` | `1–3%` | `>3%`
- 收藏/赞比：`<0.1` | `0.1–0.3` | `>0.3`（长内容：`<0.2` | `0.2–0.5` | `>0.5`）
- 回复数：`<区间>`

**一句话 reason**:
> [主驱动维度 + 最强约束 + 中枢怎么来的]

---

## 推理因素

| 因素 | 方向 | 置信度 | 说明 |
|---|---|---|---|
| `<维度或协变量>` | 强 + / 中 + / ? / 强 - | 高 / 中 / 低 | [≤30 字] |

---

## 锚点对比

| 对照帖子 | 形态 | composite | 实际（×基线） | 异同 |
|---|---|---|---|---|
| `<短名>` | `<form>` | `<X.XX>` | `<N.N×>` | [关键差异] |

> 校准池不够时写："校准池只有 N 条，无 composite ±0.7 的同形态样本。**锚点 N/A**——confidence `<等级>`，中枢仅供参考。" **不删这段。**

---

## 反事实场景

**如果 `大爆` / `小爆`**（X%）：[验证 / 推翻什么]
**如果 `命中`**（X%）：[基准线验证什么]
**如果 `持平`**（X%）：[推翻什么]
**如果 `退步`**（X%）：[可能的解释——内容还是发布条件]

---

## 关键校准假设

[对照帖子 + 关键维度差异]
**我押**：[本篇 / 对照 = N×（按各自基线倍数比）]
如果反过来 → [推翻什么]
如果差距 < 1.3× → [噪声范围]

> 没有可对照样本时写："无可对照样本，本次想测：……"

---

## 复盘

（待填——复盘窗口到期后跑 `/cheatx-retro`）
