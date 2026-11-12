# Rubric Bump Validation Protocol（升级验证协议）

被这些子 skill 引用：`cheatx-bump`、主 SKILL.md。

项目原则 #2 的完整规范——**升级 = 全量重打**。任何对 rubric 的结构性变更都必须走完本协议。

X 版和上游的区别：X 的单条结果噪声大（一次大号转发就是 30×），样本又攒得快。所以一致性检验从"几条样本排对了几条"换成**秩相关 + 自助重采样稳定性**，并由 `tools/rank_check.py` 确定性计算，不靠模型心算。

---

## "升级"的定义

触发完整 bump 流程：
- 公式系数变化（SV×1.0 → ×1.5）
- 维度增减（加 TM，删 DW）
- 维度定义颠覆性改写
- NR 扣分系数变化
- 归一化常数变化

**不**触发 bump，但要在 `rubric_notes.md` 标注：
- 维度定义边际细化（某档锚点描述更具体）
- 打分习惯备注（不改公式）

`--bucket-only`（只重算各形态基线和 bucket 边界）不是 bump，但同样记录在 `rubric-memo.md`。

---

## 何时可以提议（Claude 判断为主，以下是参考）

1. 某跨样本观察有清晰、可追溯到数据点的支持（参考 ≥5 条；1-2 条极强信号也可，如同 composite 相差 10× 且无外生冲击）
2. 最近复盘系统性同向偏差（参考连续 ≥4 次同向；X 噪声大，比上游的 3 次多一次）
3. 某候选维度（如 TM）展示独立预测力
4. 校准池跨过分水岭（10 / 25 / 50 / 100）触发常规复审

提议时**显式标注** default-aligned 还是 judgment-driven。

## 何时禁止提议

硬约束：
- `in_progress_session.type == "bump"`（上一次 bump 没走完）
- 上次 bump 后没有任何新校准样本

软建议（可打破，但要显式说明理由，仍走完 5 步）：
- 校准池 < 10 条
- 距上次 bump < 5 条新样本

---

## 完整升级流程（5 步，不许跳）

### Step 1：写出新公式的完整方程

```
v0  composite = (HK + RP + SV + RS + DW + FT + NF) / 7 × 2.0 − NR × 0.4
v1  composite = (HK×1.5 + RP + SV×1.5 + RS + DW + FT + NF) / 8 × 2.0 − NR × 0.6
```

"把 SV 权重提一点"这种不完整描述不算。

### Step 2：在校准池上重算

**校准池** = `predictions/*.md` 中有完整复盘段的文件，**排除**：
- 复盘段标了 `exogenous_boost`（外生冲击主导）
- 标了 `Integrity warning`（发出文本与预测文本差 ≥30%，或预测段被外部修改）
- reconstructed / `_redo`
- `early_retro: true` 的样本降权 0.5（不排除）

**结果变量**用 `实际曝光 / 预测时 Baseline`（倍数），不用绝对曝光——账号在长大，绝对数不可比。

- **只改系数**：维度分不变，直接用新公式重算所有样本的 composite（零成本，必须全量）
- **新增维度**：老样本需要回补新维度分。通过 `cheatx-score-blind` sub-agent 对 `drafts/<id>.md` 打新维度（盲打，不看结果）。
  - 池 ≤ 40 条 → 全量回补
  - 池 > 40 条 → 按"形态 × 结果三分位"分层抽 40 条回补，只在这 40 条上做 Step 3；表里标明抽样

### Step 3：排序一致性（确定性计算）

把样本导出成 `.cheatx-cache/bump-pool.csv`（列：`file, form, composite_old, composite_new, outcome_ratio, weight`），跑：

```bash
python tools/rank_check.py .cheatx-cache/bump-pool.csv
```

输出并判定：

| 指标 | 通过条件 |
|---|---|
| Spearman ρ（新 composite vs outcome_ratio） | ρ_new ≥ ρ_old + 0.05 |
| 新公式 ρ 本身 | ρ_new ≥ 0.25（否则新公式也只是噪声） |
| 自助重采样稳定性 | 1000 次重采样中 ρ_new > ρ_old 的比例 ≥ `THRESHOLD`（默认 **0.80**） |
| 按形态分组 | 任何样本数 ≥ 5 的形态里，ρ_new 不得比 ρ_old 低 0.10 以上（防止"整体变好、某形态崩掉"） |

`THRESHOLD = 0.80` 对应上游的"4/5 一致"——同样是刚性门槛。

### Step 4：跨模型独立审核（强制，除非 escape hatch）

`CROSS_MODEL_AUDIT=true`（默认）：
1. 调 `mcp__llm-chat__chat`，发给外部模型：旧 / 新公式、Step 3 的完整输出（含每个样本的维度分、composite 新旧、outcome_ratio、形态、协变量）
2. 外部模型独立判定：一致性是否真的达标？新公式解释力是否更强？是否只是在拟合少数极端样本？
3. 输出 **PASS** / **REJECT** + ≥100 字理由
4. 本地 Step 3 与外部审核**都通过**才进 Step 5

`CROSS_MODEL_AUDIT=false`：仅离线时用；state 标 `last_bump_self_audited: true`，cheatx-status 持续提示。

### Step 5：升级后清算

一次性完成：
1. `rubric_notes.md` 顶部更新**当前版本** + 版本速查表新增一行（只写公式与通用规则——**不写样本名、数字、链接**）
2. `rubric-memo.md` 追加"vN → vN+1 升级 Memo"（触发观察 + 证据数据 + Step 3 输出 + 外部审核理由 + 已知局限）
3. 删除已被吸收为正式维度 / 权重的观察记录
4. 删除被推翻的观察记录
5. 未解决的观察 → 移到"待验证假设"
6. 每个校准样本的预测文件**末尾**追加一行：`**Re-scored under vN+1 on YYYY-MM-DD**: composite=X.XX → Y.YY`（不碰预测段、不碰复盘段正文）
7. state：`rubric_version` +1、`last_bump_at`、`calibration_samples_at_last_bump`、清空 `consecutive_directional_errors`

---

## bump 被拒后

| 失败位置 | 处理 |
|---|---|
| Step 3 不达标 | 候选公式回到"待验证"。**不允许**调低 THRESHOLD 或改用对自己有利的指标 |
| Step 4 REJECT | 外部理由完整记进 `rubric-memo.md` 的"被拒升级 log" |
| 本地与外部冲突 | 视为 REJECT |
| Step 5 清算做不完 | 回滚——方案不成熟 |

---

## 升级阻尼

样本越多，bump 越难——这是故意的。频繁 bump = 在追噪声。健康的 rubric：bump 越来越少、每次解释的观察越来越多。

X 上尤其要警惕：一周 20 条样本，很容易看到"连续 4 条都低估"——先查是不是发帖条件变了（时段、间隔、Premium 到期、被限流），再怀疑 rubric。协变量就是为这一步准备的。

---

## 反模式（必须拒绝）

- 「跳过重算，直接换公式」 → Step 2 不可跳
- 「跳过外部审核」 → 仅 `CROSS_MODEL_AUDIT=false` 显式设置时允许
- 「只调一个权重，不算升级」 → 任何系数变化都算
- 「把那几条被大号转发的爆款也算进来，新公式才过」 → 拒绝。外生样本排除是规则，不是可选项
- 「THRESHOLD 改成 0.7」 → 改门槛本身是元层级 bump，单独走流程
