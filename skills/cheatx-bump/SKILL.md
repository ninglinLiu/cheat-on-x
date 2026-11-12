---
name: cheatx-bump
description: 提议并执行 rubric 升级或基线重算。两种模式：**完整 rubric bump**（改公式 / 维度 / 权重 / NR 系数——5 步强制：完整方程 → 校准池重算（非盲样本和新维度走 cheatx-score-blind）→ tools/rank_check.py 秩相关 + 自助重采样 → 跨模型审核 → 清算）和 **--bucket-only**（只重算各形态曝光基线，不动公式）。触发词："升级 rubric"/"bump rubric"/"调权重"/"加一个维度"/"重算基线"/"recalibrate"。
argument-hint: '--propose "<新公式>" | --bucket-only'
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep, Skill, Task, mcp__llm-chat__chat
---

# /cheatx-bump — Rubric / 基线升级

| 模式 | 触发 | 做什么 | 验证 |
|---|---|---|---|
| 完整 rubric bump | `--propose "<新公式>"` | 改公式 / 维度 / 权重 | 5 步 + 跨模型审核（强制） |
| 基线重算 | `--bucket-only` | 重算各形态曝光基线 | 确定性计算，无审核 |

严格遵守 [bump-validation-protocol.md](../../shared-references/bump-validation-protocol.md) 和 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md)。

## Phase A0：分流

- `--bucket-only` → Phase B
- `--propose "…"` → Phase 0-8
- 都没有 → 问："调公式 / 加减维度（--propose）？还是账号长大了、基线不准了（--bucket-only）？"

两条路径不混在一次操作里。

---

## 完整 rubric bump

### Phase 0：门槛

硬约束（不能破）：
- `in_progress_session.type == "bump"` 未完成 → 先处理上一次
- 上次 bump 后 0 条新校准样本 → 拒绝

软建议（可破，但要写明理由）：校准池 < 10；距上次 bump < 5 条新样本。

提议必须标 **default-aligned** 或 **judgment-driven**。

写 `in_progress_session = {"type": "bump", "started_at", "rubric_version"}`。

### Phase 1：完整方程

```
v0  composite = (HK + RP + SV + RS + DW + FT + NF) / 7 × 2.0 − NR × 0.4
v1  composite = (HK×1.5 + RP + SV×1.5 + RS + DW + FT + NF) / 8 × 2.0 − NR × 0.6
```

同时写成 `tools/calib_pool.py` 能算的表达式（`×` → `*`）：

```
OLD = "(HK + RP + SV + RS + DW + FT + NF) / 7 * 2 - NR * 0.4"
NEW = "(HK*1.5 + RP + SV*1.5 + RS + DW + FT + NF) / 8 * 2 - NR * 0.6"
```

每一处变化说清楚动机，引用 `rubric-memo.md` 里的观察 ID。

### Phase 2：校准池重算

1. 列出校准池：`python <cheat-on-x>/tools/calib_pool.py pool predictions/ --formula-old "$OLD" --formula-new "$NEW" --out .cheatx-cache/bump-pool.csv`
   - 自动排除 reconstructed / integrity / exogenous；early 样本权重 0.5
   - stderr 会报"N 条缺新公式需要的维度分"
2. **需要盲重打的样本**：
   - 新公式引入了新维度 → 所有样本都缺该维
   - header `BlindScored By` 是 `main-claude-self` / `mixed` 的样本 → 全部维度重打
3. 池 > 40 条且需要回补 → 按"形态 × 结果三分位"分层抽 40 条，只在这 40 条上回补和检验；表里注明抽样
4. 回补：对每条样本的 `Draft Path`（v2 样本用 `posts/<id>/final.md`），分批（≤ 10）调 `cheatx-score-blind`，带 `sidecar_path: .cheatx-cache/blind-scores/bump-<id>.json`。**不接受自评兜底**——Task tool 不可用就中止 bump，建议先 `--bucket-only`
5. 带上 sidecar 重新生成校准池（sidecar 里的维度分覆盖预测文件里的旧分，样本标 `rescored`）：
   ```bash
   python <cheat-on-x>/tools/calib_pool.py pool predictions/ --formula-old "$OLD" --formula-new "$NEW" \
     --rescores .cheatx-cache/blind-scores/ --out .cheatx-cache/bump-pool.csv
   ```
   stderr 不再报"缺维度分"才进 Phase 3（抽样时只保留抽中的行）
6. 诚实标注残余污染：`model_prior_warning: true`（同一模型）、`rubric_self_designed: true`（rubric 是你自己写的）——报告末尾必印"本地一致性只是 channel A/B 内的一致性，最终以 channel C 为准"

### Phase 3：排序一致性（确定性）

```bash
python <cheat-on-x>/tools/rank_check.py .cheatx-cache/bump-pool.csv
```

通过条件（都要满足）：ρ_new ≥ ρ_old + 0.05；ρ_new ≥ 0.25；自助重采样中新公式更好的比例 ≥ 0.80；任何 ≥ 5 条的形态不退步超过 0.10。

不通过 → bump 拒绝，记进 `rubric-memo.md` 的"被拒升级 log"（含完整输出），清 `in_progress_session`，结束。**不许调门槛。**

### Phase 4：跨模型审核（强制，除非 `CROSS_MODEL_AUDIT=false`）

调 `mcp__llm-chat__chat`，发：旧 / 新公式、`rank_check.py --json` 的完整输出、pool CSV（文件名可以脱敏成序号）。要求外部模型独立回答：
1. 一致性是否真的达标？
2. 新公式是否只是在拟合少数极端样本？
3. 有没有更简单的解释（协变量：时段、间隔、Premium、外链）？

输出 **PASS / REJECT + ≥ 100 字理由**。本地和外部都 PASS 才继续；冲突视为 REJECT。

`CROSS_MODEL_AUDIT=false`（离线）→ state `last_bump_self_audited: true`，cheatx-status 持续提醒。

### Phase 5：落地 + 清算

**5a `rubric_notes.md`（只放通用语言）**
- 版本表加一行；公式段换成新方程；新维度加完整定义和 0 / 3 / 5 锚点描述
- 写完：`python <cheat-on-x>/tools/leak_check.py rubric_notes.md`——非 0 → 回滚本步，改写成更抽象的说法

**5b `rubric-memo.md`（append，不动旧 Memo）**
6 个组件：触发观察、证据（rank_check 输出 + pool 表，可以带帖子名和数字）、诊断、新公式、外部审核结论、已知局限。

**5c 清算**（observation-lifecycle）
- 被吸收的观察 → 删
- 被推翻的 → 删
- 未解决的 → 迁到"待验证假设"
- 已验证但不改公式的 → **抽象化**后进 `rubric_notes.md` 规律沉淀区（再跑 leak_check）

**5d 自检**：重读 `rubric_notes.md`，60 秒内能看懂当前规则？

### Phase 6：样本留痕

每个进池样本的预测文件**末尾**追加一行（不碰预测段、不碰复盘段正文）：

```markdown
**Re-scored under v1 on 2026-12-01**: composite=7.60 → 8.05（blind: reused | rescored）
```

### Phase 7：state

```json
{
  "rubric_version": "v1",
  "last_bump_at": "<ISO>",
  "last_bump_self_audited": false,
  "calibration_samples_at_last_bump": <当前>,
  "consecutive_directional_errors": [],
  "in_progress_session": null
}
```

### Phase 8：报告

```
✅ rubric v0 → v1
   变化：SV ×1.0 → ×1.5；HK ×1.0 → ×1.5；NR 系数 0.4 → 0.6
   校准池 34 条（排除 4：外生 2、integrity 1、reconstructed 1）
   Spearman ρ 0.21 → 0.38 · 重采样稳定性 0.91 · 各形态无退步
   外部审核：PASS（理由摘录：…）
   清算：删 3 条观察、迁 2 条到待验证、沉淀 1 条规律

之后的预测都按 v1；已写好但未发布的预测保持 v0（header 里有版本号，复盘时按各自版本对照）。
```

---

## Phase B：`--bucket-only`（基线重算）

基线是数据派生量，不是规则，所以不走审核。

1. ```bash
   python <cheat-on-x>/tools/calib_pool.py baseline predictions/ --json
   ```
   每个形态最近 10 条（排除 reconstructed / integrity / exogenous）的曝光中位数；样本 < 3 的形态为 null（回落 `all`）
2. 展示新旧对比，用户确认：

   ```
   形态      旧基线   新基线   样本
   single    420      610     10
   thread    —        1,850    4
   all       460      700     17
   确认更新？
   ```
3. 写 `state.baseline_impressions` + `baseline_updated_at`；`rubric-memo.md` 的"基线 / bucket 重算记录"追加一行
4. 只影响**之后**的预测；已写的预测按它 header 里的 Baseline 复盘

不做：不改公式、不改维度、不动 `consecutive_directional_errors`。

---

## Key Rules

1. 完整方程，不许"调高一点"
2. 回补和非盲样本重打必须走 sub-agent；Task 不可用 → 中止
3. 一致性由 `rank_check.py` 算，不靠心算；门槛不许调
4. 外部审核强制（除离线）
5. rubric_notes.md 写完必跑 leak_check
6. 清算和升级在同一次操作里完成

## Refusals

- 「跳过重算直接换公式」 → 拒绝
- 「跳过外部审核」 → 仅 `CROSS_MODEL_AUDIT=false`
- 「只调一个权重不算升级」 → 算
- 「把被大号转发的那几条也算进池子，不然过不了」 → 拒绝，排除外生样本是规则
- 「THRESHOLD 改成 0.7」 → 元层级 bump，单独走流程
- 「主 Claude 直接回补维度，sub-agent 太慢」 → 拒绝

## Integration

- 触发：`/cheatx-retro` Phase 8 提议、`/cheatx-status` 偏差提示、用户主动
- 读：`rubric-memo.md`（观察、证据）、`predictions/*.md`
- 写：`rubric_notes.md`、`rubric-memo.md`、预测文件末尾留痕行、state
