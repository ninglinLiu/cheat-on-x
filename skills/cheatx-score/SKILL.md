---
name: cheatx-score
description: 给一条（或几条）X 草稿打 rubric 分。**只在控制台输出，不写文件，不预测**。用来改稿时快速看分数、比较几个版本的第一行。触发词："打分这条 [path]"/"score this"/"先打分看看"/"这两个开头哪个好"。是 cheatx-predict 之前的轻量探索。
argument-hint: '<draft-path...>'
allowed-tools: Read, Glob, Grep, Task
---

# /cheatx-score — 打分（不预测）

快速看草稿在当前 rubric 下的 8 维分和 composite，决定要不要改、改哪里。

## Constants

- **RUBRIC_PATH = rubric_notes.md**
- **OUTPUT_DETAIL = full**（`compact` 只给分数表）
- **MAX_VARIANTS = 5**——"这几个开头哪个好"一次最多比 5 个版本

## Workflow

### Step 1：前置检查

1. 没有 `.cheatx-state.json` → 先 `/cheatx-init`
2. 草稿存在且非空；没有 frontmatter → 问形态（不写文件，只在本次打分用）
3. 读 `rubric_notes.md` 当前公式；结构被手改得认不出 → 问用户公式是哪一行，**不猜**

### Step 2：委派 cheatx-score-blind

主对话已被污染，不在这里打分。Task prompt 只含草稿路径和 rubric 路径（契约见 [cheatx-score-blind](../cheatx-score-blind/SKILL.md)）。

**比较开头 / 版本**：把每个版本存成临时草稿 `.cheatx-cache/blind-input/variant-<n>.md`（只改第一屏，其余相同；带同样的 frontmatter），一次传给 sub-agent。sub-agent 会独立给每份打分。

发送前自检 prompt：不含数字 + 曝光 / views / 万、handle、predictions 或 report 路径。

### Step 3：解析 + review

1. 解析 JSON；`self_check.any_contamination_signal` → 警告
2. 按公式用**盲分**算 composite
3. 不改 sub-agent 给的分。用户不同意某维 → 在输出里并列"你的看法"，但 score 不落盘，不需要裁定流程
4. `refusal` → 按 cheatx-score-blind 的表处理

### Step 4：输出

```
📊 ai写作清单（thread · rubric v0）

| 维度 | 分 | 理由（盲打） |
|---|---|---|
| HK 首屏钩子 | 4 | 首条「删掉的 7 个提示词」 |
| RP 回复牵引 | 3 | 可补充，但没留分歧点 |
| SV 收藏私信 | 5 | 7 条可直接复制 |
| RS 转引身份 | 3 | 圈内实用 |
| DW 停留密度 | 4 | 一条一个点 |
| FT 关注转化 | 4 | 「我用了半年」 |
| NF 圈层契合 | 5 | AI 写作工具（低置信：sub-agent 看不到账号定位） |
| NR 负反馈风险 | 1 | 结尾「转给需要的人」 |

composite = (4+3+5+3+4+4+5)/7×2 − 1×0.4 = **7.60**

最该改的：RP 3 → 第 7 条留一个有分歧的问题（"你会删哪个？"比"欢迎补充"好）；NR 1 → 删掉结尾求转发
下一步：改完再打一次，或 "启动预测"
```

**比较版本时**：一张表，每行一个版本，列 HK / NR / composite，指出差异来自哪一维。

### Step 5：绝不做

- ❌ 写任何文件（临时变体放 `.cheatx-cache/blind-input/` 除外，用完删）
- ❌ 给 bucket 或概率（那是 predict 的事）
- ❌ 碰发布 / 复盘
- ❌ 提议改 rubric

## Key Rules

1. 打分走 sub-agent
2. 整数分
3. 理由是诊断工具——"最该改的"必须指向具体维度和具体句子
4. 不写文件

## Refusals

- 「打分顺便预测一下」 → 改用 `/cheatx-predict`
- 「打完把分写进 rubric_notes.md」 → 拒绝。观察需要"预测 vs 实际"，光有分数不算
- 「直接告诉我会不会爆」 → 拒绝。要 bucket 就走 predict
- 「跳过 sub-agent 直接打」 → 不接受。score 是轻量探索，没理由放弃隔离；Task tool 不可用就先配置

## Integration

- 无副作用，可以反复跑
- 同一条连续打分 ≥ 3 次 → 温和提醒"差不多可以定了"
- 下游：`/cheatx-predict`
