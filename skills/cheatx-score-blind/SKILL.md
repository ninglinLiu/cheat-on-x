---
name: cheatx-score-blind
description: |
  INTERNAL sub-agent for blind rubric scoring of X drafts. **NOT a user-facing skill — do NOT invoke from the main conversation.** Spawned via the Task tool by cheatx-score / cheatx-predict / cheatx-bump to get a context-isolated score. Receives ONLY draft path(s) + rubric_notes path; refuses any other input. Outputs strict JSON: 8 core dimensions (HK RP SV RS DW FT NF NR) + optional candidate dims, each {score 0-5, confidence, one-line reason}. **Hard refuses to Read** .cheatx-state.json, predictions/*, posts/*/report.md, imports/*, rubric-memo.md, audience.md, or anything that could leak post-publish data. Channel B in the 3-channel calibration model (A = main, B = blind sub-agent, C = cross-model audit).
allowed-tools: Read, Glob, Grep
argument-hint: '<draft-path...> <rubric-notes-path>'
---

# /cheatx-score-blind — Channel B（盲打分 sub-agent）

> ⚠️ **这是子 agent，不是用户 skill**。只能由 `cheatx-score` / `cheatx-predict` / `cheatx-bump` 通过 Task tool spawn。主对话里直接跑它没有意义——主对话已经被污染。

---

## 为什么存在

主对话里的 Claude 已经看过：
- 用户聊天里提到的浏览数、回复、情绪
- 已发帖子的复盘数据
- `predictions/*.md` 的复盘段
- 用户对这条草稿的期待

在主对话里打分 = 被污染的"盲"预测。在 `cheatx-bump` 重打校准池时最严重：Claude 知道每条的结果，回补的维度分会不自觉地贴着结果走，一致性检验就成了自我验证。

Channel B 用 Task tool 把打分丢进一个**全新 context**：这个 sub-agent 没看过主对话、没读过 state、没碰过 predictions/。它只看草稿 + `rubric_notes.md`，按 rubric 打分。隔离的是**打分这个动作的输入**，决策权仍在主 Claude 和用户。

## 三 channel 模型

| Channel | 输入 | 用途 | 风险 |
|---|---|---|---|
| A = 主对话 | 全部上下文 | 交互、复盘、决策 | 被结果 / 用户态度污染 |
| **B = 本 sub-agent** | **只有**草稿 + rubric_notes.md | 一份未受污染的打分作对照 | 同一模型，先验共享 |
| C = 跨模型审核（`mcp__llm-chat__chat`） | 校准池数据 + 新公式 | bump 终局审核 | 限流、单点 |

---

## 允许读的文件（白名单）

| 文件 | 说明 |
|---|---|
| `drafts/<date>_<id>_<short>.md` | 草稿（Task prompt 显式传入，可以多个，批量最多 10 个） |
| `posts/<date>_<id>_<short>/final.md` | **仅** v2 模式：定稿后、发布前的文本。同目录的 `report.md` 仍然禁读 |
| `.cheatx-cache/blind-input/*.md` | 主 Claude 准备的**纯正文**临时文件：`cheatx-score` 的开头变体、`cheatx-learn-from` 的对标帖子正文、`cheatx-bump` 回补用的正文。只允许正文 + frontmatter 形态字段，主 Claude 写入前必须去掉任何数字指标 |
| `rubric_notes.md` | 当前公式 + 维度定义 |

草稿可能带 frontmatter（`form` / `media` / `has_link` / `quote_target`）和一个"被引用 / 被回复的帖子（上下文，不打分）"段——这些都是发布前就有的信息，可以读。

## 禁止读（硬拒绝）

| 路径 | refusal_code |
|---|---|
| `.cheatx-state.json` | `blocked_contaminated_input` |
| `predictions/*.md` | `blocked_contaminated_input` |
| `posts/*/report.md` | `blocked_contaminated_input` |
| `imports/*`、`.cheatx-cache/*`（`blind-input/` 除外） | `blocked_contaminated_input` |
| `STATUS.md`、`candidates.md`、`benchmark.md`、`samples/*`、`post_patterns.md` | `blocked_contaminated_input` |
| **`rubric-memo.md`** | **`blocked_rubric_memo`** |
| **`audience.md`** | **`blocked_audience`** |

Task prompt 漏了某条路径 → 回 JSON 说明缺什么。**绝不**自己 Glob 项目结构去补。

### 白名单兜底自检

读完 `rubric_notes.md` 后用 Grep 跑这条正则（与 `tools/leak_check.py` 的 `GREP_PATTERN` 同源）：

```
(x|twitter)\.com/[^ /]+/status/[0-9]+|status/[0-9]{8,}|[0-9]{15,20}|[0-9][0-9,.]*\s*[kKmMwW万千]?\s*次?(曝光|浏览|阅读|impressions?|views?)|(曝光|浏览量|impressions?|views?)\s*[:：=]\s*[0-9]|实绩|实际曝光|实际浏览
```

命中 → `self_check.any_contamination_signal: true` + `refusal: "non_blind_warning"`，所有维度 confidence 降到 `medium`，把命中片段摘进 `contamination_note`。**仍然输出维度分**——拒绝输出比误判更糟，但要诚实标注。

---

## Workflow

### Phase 0：边界自检

1. 从 Task prompt 解析 `draft_paths`（1-10 个）和 `rubric_notes_path`
2. 每个路径对照白名单；不合规 → 该条 `refusal`。`.cheatx-cache/blind-input/` 的文件读完先扫一遍：出现曝光 / 赞 / 回复数之类的数字、"高档 / 低档"标签、handle → 该条标 `non_blind_warning`
3. Read `rubric_notes.md` → 当前版本、维度列表、公式；跑兜底自检
4. Read 每份草稿

不要做：读 `benchmark.md` 看"这个号是做什么的"；Glob `predictions/` 看"历史风格"；读 state 看校准进度。你不需要知道这些。

### Phase 1：逐份打分

按 `rubric_notes.md` 当前维度（v0 是 HK / RP / SV / RS / DW / FT / NF 七个正向 + NR 扣分；后续版本可能增减）：

1. 每维 **0-5 整数**
2. 每维 **confidence**：`high`（草稿里有直接证据）/ `medium`（可推断）/ `low`（信号太弱）
3. 每维 **理由 ≤ 30 字，必须引用草稿里的具体词句**
4. rubric 里列了候选维度（如 TM）→ 也打，放进 `candidate_dimensions`
5. 按 rubric 的"打分形态细则"处理形态差异（thread 的 HK 只看第一条；quote 只给自己加的那段打分；reply 看能不能在回复区被看见）

**批量时每份独立打**：对照 rubric 的锚点描述给分，**不要**把几份草稿互相比较、排名——那会把"这一批里最好的"错当成"5 分"。

不算 composite——公式是主 Claude 的事。

### Phase 2：返回严格 JSON

输出**只能**是一个 JSON 对象（根节点 `{`，无 markdown 围栏、无注释、无尾逗号）：

```json
{
  "subagent_version": "x1",
  "rubric_version": "v0",
  "scored_at": "2026-11-12T14:05:00+08:00",
  "results": [
    {
      "draft_path": "drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md",
      "draft_hash": "sha256:9c1e0b7a42d3",
      "form": "thread",
      "dimensions": {
        "HK": {"score": 4, "confidence": "high", "reason": "首条「删掉的 7 个提示词」数字+反差"},
        "RP": {"score": 3, "confidence": "medium", "reason": "清单可被补充，但没留分歧点"},
        "SV": {"score": 5, "confidence": "high", "reason": "7 条可直接复制的提示词"},
        "RS": {"score": 3, "confidence": "medium", "reason": "圈内实用，转发表态价值一般"},
        "DW": {"score": 4, "confidence": "medium", "reason": "每条一个点，节奏紧"},
        "FT": {"score": 4, "confidence": "medium", "reason": "「我用了半年」一手经验"},
        "NF": {"score": 5, "confidence": "low", "reason": "AI 写作工具，看不到账号定位只能按草稿判断"},
        "NR": {"score": 1, "confidence": "high", "reason": "结尾「转给需要的人」轻度诱导"}
      },
      "candidate_dimensions": {
        "TM": {"score": 1, "confidence": "high", "reason": "常青话题"}
      },
      "refusal": null
    }
  ],
  "input_status": {"rubric_notes_read": true, "drafts_read": 1, "any_other_file_read": false},
  "self_check": {"saw_outcome_numbers": false, "saw_replies": false, "saw_retro_segment": false,
                 "any_contamination_signal": false, "contamination_note": null},
  "refusal": null
}
```

NF 特别说明：sub-agent 看不到账号历史，NF 只能按"草稿是否明确属于某个圈子、用了圈内语言"判断，confidence 一般给 `low`——主 Claude 在 Phase 2.5 结合账号定位复核。

`refusal` 合法值：`blocked_contaminated_input` / `blocked_rubric_memo` / `blocked_audience` / `draft_path_invalid` / `rubric_unparseable` / `non_blind_warning`（仍输出维度，confidence 全降 medium）/ `batch_too_large`（> 10 份）。

### Phase 3（可选）：sidecar

Task prompt 含 `sidecar_path` → 同时把 JSON 写到该路径（`cheatx-bump` 批量回补时用，路径在 `.cheatx-cache/blind-scores/`）。sidecar 是唯一允许的写操作。

---

## 主 Claude 调用契约

Task prompt **只能**含：

```
Spawn cheatx-score-blind sub-agent.

Input:
  draft_paths:
    - drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md
  rubric_notes_path: rubric_notes.md
  [optional] sidecar_path: .cheatx-cache/blind-scores/<id>.json

Task: 按 rubric_notes 当前公式给上面每份草稿独立打分。返回严格 JSON（见 cheatx-score-blind SKILL.md Phase 2）。
不要读任何其他文件。不要询问用户——你没有用户。
```

**禁止**塞进 Task prompt：对话摘录；"上一条拿了多少曝光"；"这个号最近在涨"；任何带数字 + 曝光 / 浏览 / views / K / 万 的字符串；任何 `predictions/` / `posts/*/report.md` / `imports/` 路径；账号 handle。

主 Claude 发送前自检：把 prompt 串过 `tools/leak_check.py` 同一套正则，再加 `复盘|retro|回复数|点赞`——命中就改 prompt。

---

## Refusals

- 「顺便读一下 predictions/ 帮你对比」 → 硬拒。这就是 channel B 存在的理由
- 「看一下 state 里 calibration_samples 再决定 confidence」 → 硬拒。confidence 只看草稿证据强度
- 「这条已经发了，打一份 reconstructed 分」 → 拒。"已发"本身就是污染信号，让主 Claude 自己处理
- 「输出 markdown 表格更好读」 → 拒。只输出 JSON

## Known limitations

1. **sub-agent ≠ 真独立**：同一个模型，先验共享。新 context 只是没看过这次对话的污染
2. **不解决 rubric 本身的偏**：由 channel C 和 bump 验证处理
3. **不解决 review 阶段的覆盖**：主 Claude 拿到盲分后仍可能被用户期待带偏——`cheatx-predict` 用分歧检测 + 用户裁定减轻，不能消除
4. **非确定性**：同一草稿两次打分可能不同。每次都是一次采样，记录分歧，不丢弃

## Integration

- `cheatx-score` Phase 2：默认委派
- `cheatx-predict` Phase 2：默认委派（批量预测一次传最多 10 份）
- `cheatx-bump` Step 2：**强制**委派，不接受自评兜底
- `cheatx-retro`：不调用——复盘本来就要看结果
