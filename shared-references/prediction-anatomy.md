# Prediction Anatomy（预测日志解剖）

被这些子 skill 引用：`cheatx-predict`、`cheatx-retro`、`cheatx-publish`、`templates/prediction.template.md`。

**所有预测都用统一结构**——7 个组件 + 复盘段。两种模式只在"写多少"上不同，标题一个不少：

| 模式 | 用在 | 组件 4-7 的写法 |
|---|---|---|
| `full`（完整预测） | thread / 长帖 / Article / 你特别在意的帖子 | 完整写 |
| `quick`（快押） | 日常短帖、回复、批量预测 | 每个组件允许一行；锚点、反事实、校准假设可以写成一句 |

Confidence 等级（从 `calibration_samples` 派生，见 [state-management.md](state-management.md)）作为 header 字段标注，**不改变结构**。

> 为什么快押也要保留 7 个标题：复盘时 `cheatx-retro` 按组件逐项对照。标题在、内容短，比"快押没有反事实"更好——一行反事实也能在复盘时告诉你哪个假设被测了。

---

## 文件与命名

```
drafts/<date>_<id>_<short>.md         ← 草稿
predictions/<date>_<id>_<short>.md    ← immutable 预测（本文件）
posts/<date>_<id>_<short>/            ← 定稿后才建（cheatx-queue）
  ├── final.md                        ← 实际要发的文本
  └── report.md                       ← 复盘数据（cheatx-retro / 导入器写）
```

- `<date>`：草稿首次落盘日期
- `<id>`：草稿首次落盘内容的 sha256 前 12 位。之后改草稿 id 不变
- `<short>`：3-8 字短名
- Reconstructed 重做：`<short>_redo`，三处都加；原文件保留

---

## 组件 1：File header（文件头）

`## ` 标题之前的所有行是 header。hook 允许改 header（发布登记要往这里加字段），不允许改 `## 预测` 段。

```markdown
# AI 写作清单 — 预测日志

**Post ID**: a3f2c1d4e5b6
**Short**: AI 写作清单
**Form**: thread (7)
**Media**: image
**Has Link**: no
**Reply/Quote Target**: n/a
**Rubric Version**: v0
**预测时间**: 2026-11-12T14:05+08:00
**Planned Post Time**: 2026-11-12T21:00+08:00（周三晚）
**Draft Path**: drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md
**Draft Hash**: sha256:9c1e0b7a42d3
**Text Length**: 1,180 字 / 7 条
**Followers at Predict**: 1,240
**Premium**: premium
**Baseline**: thread=n/a（不足 3 条）→ all=420（最近 10 条中位数）
**Calibration Samples (at predict time)**: 6
**Confidence**: 🟡 偏低（中枢 ±40%）
**Prediction Mode**: full
**Prediction Basis**: pre_publish
**Scored By**: claude
**BlindScored By**: subagent-v1
**BlindScore Disagreement**: [{"dim":"HK","blind":4,"self":4,"delta":0,"decided_as":4}, …]
**User Override**: none
**预测时数据状态**: **blind**（这条帖子尚未发布）
```

字段规则：
- `Form` 取 `single` / `thread (N条)` / `long` / `article` / `quote` / `reply`
- `Reply/Quote Target`：reply / quote 必填对方 handle + 粉丝量级（如 `@abc（~120k）`）；其他形态写 `n/a`
- `Baseline`：写清用的是哪一级（form / all / cold-start guess）和数值——bucket 边界由它派生
- `Followers at Predict` / `Premium` / `Planned Post Time` / `Has Link` / `Media`：协变量，bump 时解释残差用
- `Prediction Basis`：`pre_publish`（v1，标准盲预测）/ `pre_publish_v2`（定稿时改动 ≥30% 触发的 v2，仍未发布）
- `BlindScored By`：`subagent-v1`（默认）/ `main-claude-self`（`--skip-blind` 或用户在分歧裁定时选主估）/ `mixed`
- `BlindScore Disagreement`：**每个维度一条，delta=0 也要记**（8 个核心维度；TM 候选维度记了也写）
- `预测时数据状态`：必填。如果帖子已经发出（不推荐），写 `blind（已发布 N 分钟，确认未看任何数据）`+ `published_before_prediction: true`

**发布后由 `/cheatx-publish` 追加到 header 末尾**（不碰预测段）：

```markdown
**Published at**: 2026-11-12T21:03+08:00
**Status ID**: 1988765432109876543
**URL**: https://x.com/yourhandle/status/1988765432109876543
**Post Folder**: posts/2026-11-12_a3f2c1d4e5b6_ai写作清单/
**Posted Text Check**: same | diff 12% | diff 41% ⚠️ | unchecked
**Minutes Since Previous Post**: 95
**Retro Due**: 2026-11-14T21:03+08:00
```

---

## 组件 2：输入快照

```markdown
## 输入快照

**分数 (v0)**: HK4 / RP3 / SV5 / RS3 / DW4 / FT4 / NF5 / NR1 → composite=**7.60**（28/7×2 − 0.4）
**候选维度（不进公式）**: TM1

**用户改写要点 vs Claude 草稿**:
- 第一条：用户把"最近在用 AI 写作"改成了具体工具数和节省时间
- 砍掉：第 5 条的个人感慨
- 保留：清单结构
```

用户从零写的 → "用户原创稿，无 Claude 草稿对照"。

---

## 组件 3：预测主体 ⭐ immutable

`hooks/prediction-immutability.sh` 拦截从 `## 预测` 到下一个非预测 `##` 之间的任何改动。

```markdown
## 预测 v1

**Bucket**: `命中`（1–3× 基线 → 420–1,260 曝光）
**中枢**: 800

**概率分布**:
- `退步`（<126）→ 10%
- `持平`（126–420）→ 30%
- **`命中`（420–1,260）→ 40%**
- `小爆`（1,260–4,200）→ 15%
- `大爆`（>4,200）→ 5%

**次要押注**:
- 互动率：`1–3%`
- 收藏/赞比：`>0.3`
- 回复数：`5–15`

**一句话 reason**:
> SV=5 的工具型清单在本圈子收藏率高；HK=4 第一条有具体数字；thread 第一次发、无同形态基线，中枢按 all 基线 ×1.9。
```

强制要求：
- **Bucket** 是 5 个倍数桶之一（`退步` / `持平` / `命中` / `小爆` / `大爆`），括号里写换算后的曝光区间
- **概率加起来 100%**
- **中枢**写成具体曝光数
- confidence 低 → 分布应该更平（如 20/30/25/15/10），不是更尖
- 次要押注：`full` 必填三项；`quick` 可只写互动率或省略（写"省略"）

---

## 组件 4：推理因素表

```markdown
## 推理因素

| 因素 | 方向 | 置信度 | 说明 |
|---|---|---|---|
| SV=5 | 强 + | 中 | 7 个可复制的提示词，收藏动机明确 |
| thread 形态 | ? | 低 | 账号第一次发 thread，第一条之后的点开率未知 |
| 发帖时段 21:00 | 中 + | 低 | 之前晚间帖子偏好，样本少 |
| 距上一条 95 分钟 | 弱 - | 低 | 作者多样性衰减可能还在 |
```

置信度：高（强证据 + 多锚点）/ 中（有理由但样本少）/ 低（直觉）。复盘时"低置信度"被验证 → 直觉强；"高置信度"被推翻 → rubric 有 bug。

快押：一行，如 `| HK=5 + NF=5 | 强 + | 低 | 核心话题 + 第一行就是结论 |`。

---

## 组件 5：锚点对比

找 2-4 条 composite 接近、**形态相同优先**的已复盘帖子：

```markdown
## 锚点对比

| 对照帖子 | 形态 | composite | 实际（×基线） | 异同 |
|---|---|---|---|---|
| 提示词模板 | single | 7.0 | 2.1× | 同为 SV 主导，本篇是 thread |
| 周报自动化 | single | 7.4 | 0.6× | 同 composite，但 NF=3（偏离核心话题） |
```

"实际"一栏写**相对当时基线的倍数**，不写绝对数——账号在长大，绝对数不可比。

校准池不够时 **仍写这段**：

```markdown
## 锚点对比

校准池只有 N 条，无 composite ±0.7 的同形态样本。**锚点 N/A**——本次 confidence 🔴/🟠，中枢仅供参考。
```

---

## 组件 6：反事实场景

```markdown
## 反事实场景

**如果 `大爆` / `小爆`**（20%）：说明清单类 thread 在本圈子有破圈能力 → SV 权重可能该上调；检查是否被单个大号转发（外生）
**如果 `命中`**（40%）：基线判断成立
**如果 `持平`**（30%）：thread 第一条之后的点开率低，HK 只覆盖第一条的设计需要复审
**如果 `退步`**（10%）：可能是发帖间隔太短 / 时段问题，而不是内容
```

为什么必填：实际落在哪个 bucket，直接告诉你哪个假设被测试了。快押写一行即可：`爆 → SV 被低估；退步 → 时段/间隔问题`。

---

## 组件 7：关键校准假设

```markdown
## 关键校准假设

对照「周报自动化」（同 composite 7.4，NF 3 vs 本篇 5）：
**我押：本篇 / 对照 ≥ 2×（按各自基线倍数比）**
如果反过来 → NF 的作用被高估
如果差距 < 1.3× → NF 影响在噪声内
```

没有可对照样本 → "无可对照样本，本次想测：thread 形态相对单帖的倍数"。**不删这段**。

---

## 组件 ∞：复盘段（仅追加）

复盘窗口到期后由 `/cheatx-retro` 追加。**不修改预测段任何字符**。

```markdown
## 复盘

**复盘时间**: 2026-11-14T21:10+08:00（发布 T+48h）
**数据快照时间**: 2026-11-14T20:55+08:00（距发布 47.9h）
**数据来源**: csv:userscript（imports/x-posts-20261114.csv）
**有效预测段**: 预测 v1

### 实际数据
- 曝光：**2,130** → 落在 `小爆`（预测 `命中`）；实际 / 中枢 = **2.66×**
- 实际 bucket 的预测概率：15%（log score −1.90）
- 赞 54 · 转 9 · 引用 3 · 回复 17 · 收藏 31
- 互动率 5.4%（押 1–3% ❌）· 收藏/赞比 0.57（押 >0.3 ✅）· 回复 17（押 5–15 ❌ 偏高）
- 主页访问 38 · 新增关注 6（数据来源有才写）
- 外生冲击：无

### 回复与引用
- 补充型（"还可以加 X"）：9 条，最高 12 赞
- 求模板：4 条
- 反对：1 条

### 哪些预测被验证 ✅ / 推翻 ❌
（每条引用具体数字）

### 需要写进 rubric-memo.md 的新观察
1. ……

### Bump 触发评估
- 偏差方向：low（低估，2.66× 超出 2× 门槛）
- 累计同向：2 次
- 是否提议 bump：否
```

偏差判定（X 版）：
- `实际 / 中枢` 在 **0.5 – 2×** 之间 → on-target（倍数桶本身就是 3× 宽，±25% 的门槛在 X 上会把几乎所有预测都判成偏差）
- < 0.5× → `high`（高估）；> 2× → `low`（低估）
- ≤ 0.2× 或 ≥ 5× → 极端偏差
- 外生冲击（被大号转发 / 引用主导）→ 记录但**不计入**连续同向偏差

---

## v1 / v2 段约定

- 新建文件写 `## 预测 v1`
- v2 触发：`/cheatx-queue` 定稿时，定稿与草稿的归一化字符差异 ≥ 30% → 调 `/cheatx-predict — mode: v2`，在 `## 复盘` 之前追加 `## 预测 v2`
- v1 **绝不**修改；复盘用最后一个 `## 预测 vN`
- v2 仍然必须在发布**之前**写

## 发出文本与预测文本不一致

`/cheatx-publish` 拿到发出的正文后（从导出 CSV 或 API，只取正文不取指标）和预测时的定稿比：
- 差异 < 10% → `Posted Text Check: same`
- 10–30% → `diff N%`，复盘段照常
- ≥ 30% → `diff N% ⚠️`，复盘段加 **Integrity warning**，该样本 bump 时降权（它测的不是你预测的那条）

---

## 子 skill 验收标准

`cheatx-predict` 写完自检：7 个组件标题齐全；header 必填字段齐全；概率加和 100%；bucket 区间按 Baseline 算对。

`cheatx-retro` 复盘前校验：有 `Published at` 和 `Status ID`；缺组件 → 警告"预测不规范，复盘价值打折"。
