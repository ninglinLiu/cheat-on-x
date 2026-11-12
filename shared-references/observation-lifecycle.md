# Observation Lifecycle（观察生命周期协议）

被这些子 skill 引用：`cheatx-retro`、`cheatx-bump`、`cheatx-status`、主 SKILL.md。

项目原则 #3 的完整规范——**rubric 是工作台，不是博物馆**。

---

## 两个文件，各管一半

| 文件 | 放什么 | 谁能读 |
|---|---|---|
| `rubric_notes.md` | 当前公式、维度定义、bucket 规则、**抽象后的**规律沉淀（不带样本名、不带数字） | 所有人，包括 blind 打分 sub-agent |
| `rubric-memo.md` | 观察记录、跨样本观察、待验证假设、升级 Memo、被拒升级 log——**带样本名和实际数据** | 主对话；blind sub-agent **硬禁读** |

观察一开始带着数据，所以只能住在 `rubric-memo.md`。只有等它被 bump 流程确认、并且抽象成不带数据的通用规则后，才搬进 `rubric_notes.md`。

---

## 生命阶段

```
[复盘新增] → [观察记录] → [跨样本观察] → [规律沉淀（抽象后进 rubric_notes）] / [吸收为维度或权重] / [被推翻 → 删]
                                     ↘
                                      [待验证假设]（暂存）
```

| 阶段 | 位置 | 触发 |
|---|---|---|
| 观察记录 | `rubric-memo.md` → `## 观察记录` | 每次复盘一条（批量复盘时可以一组帖子合写一条，注明各自 id） |
| 跨样本观察 | `rubric-memo.md` → `## 重大跨样本观察` | 同一 pattern 在 ≥3 条样本里出现 |
| 待验证假设 | `rubric-memo.md` → `## 待验证假设` | 有信号但还没复现 |
| 规律沉淀 | `rubric_notes.md` → `## 规律沉淀区` | 通过 bump 流程确认、无需改公式；**写入前必须抽象化** |

---

## 升格门槛（Claude 判断为主，下面是默认参考）

X 样本多、单条噪声大，默认门槛比上游高一档：

| 从 → 到 | 默认 | 可软违反的强信号 |
|---|---|---|
| 观察记录 → 跨样本观察 | 同 pattern ≥3 条 | 2 条 + 回复区出现大量同类回应（如同一种补充 / 同一种反对） |
| 跨样本观察 → 规律沉淀 | ≥5 条 + 不需要改公式 + bump 流程确认 | — |
| 跨样本观察 → 维度 / 权重 | ≥5 条 + 通过 bump | 见 bump-validation-protocol |
| 任意 → 删除 | 被推翻 / 被吸收 / 被沉淀 | bump cleanup pass |

外生冲击样本（被大号转发主导）和 Integrity warning 样本**不算**支持样本，只能作旁证。

软违反时标注 `**Promoted with N samples (default expects M)**: <理由>`。最近 3 次升格里有 2 次软违反 → cheatx-status 提示"升格判断可能太激进"。

### 校准池规模 → 允许的改动

| 校准池 | 允许 |
|---|---|
| 1-4 条 | 只记单次观察 |
| 5-14 条 | 候选规律；修正维度定义（定性）；**第一次 bump** 一般在这一档 |
| 15-39 条 | 权重微调 ±0.5 |
| 40+ 条 | 用 `tools/rank_check.py` 的秩相关 / 回归做数据驱动 bump |

---

## 删除规则

**必须删**：
- **被吸收为维度或权重的观察**——维度本身就是它的新归宿，保留等于同一概念出现两次
- **被新数据推翻的观察**——保留会让未来按错误规则打分

**保留**：
- 未解决的观察 → bump 时迁到"待验证假设"
- 历史校准事件（"v0 → v1 是因为 SV 系统性低估"）→ 写在升级 Memo 里，不留在观察段
- 仍生效的规律 → 规律沉淀区

## 反模式（拒绝）

| 反模式 | 为什么不行 |
|---|---|
| `~~SV ×1.0~~ 改为 ×1.5`（删除线旧值） | 旧值看 git history |
| "我曾经以为 RP 重要，但其实……" | 读者读完不知道现在的规则 |
| "先放着，下次 bump 再删" | bump 落地的同一次操作里删干净 |

---

## Blind channel leak guard（写 `rubric_notes.md` 时必须遵守）

`rubric_notes.md` 是 `cheatx-score-blind` sub-agent 的白名单。里面只要出现一条真实帖子的结果，sub-agent 的"盲"就破了。

**禁止写入 `rubric_notes.md`**：

| 模式 | 例子 | 应该写到 |
|---|---|---|
| 真实帖子 + 结果 | "「提示词清单」曝光 2,130" | rubric-memo.md |
| 帖子链接 / status id | `x.com/abc/status/1988…` | rubric-memo.md |
| 带命名锚的派生证据 | "「周报自动化」NF=3 → 0.6×" | rubric-memo.md |
| bump 重算表 | 样本对照表 | rubric-memo.md |
| 回复原文 | "有人回复『求模板』" | rubric-memo.md |

**允许**：公式；维度定义和锚点描述；bucket 规则（倍数）；抽象后的规律（"清单类 thread 的 SV 常被低估一档"）；观察 ID + 一句话（不带样本名、不带数字）。

**强制自检**：任何 skill 写完 `rubric_notes.md` 后跑

```bash
python tools/leak_check.py rubric_notes.md
```

退出码非 0 → abort 并回滚这次写入。`tools/leak_check.py` 里的正则是唯一真值；`cheatx-score-blind` 用同一条正则做读后自检。

> 上游历史教训：cheat-on-content 曾经把 bump Memo 写进 rubric_notes.md，blind sub-agent 通过白名单读到了实绩（上游 PR #11 / #12）。X 版从第一天就拆成两个文件。

---

## cleanup pass

强制：bump 落地最后一步；用户显式要求"清算"。
建议：校准池每加 15 条看一次；`rubric_notes.md` 超过 300 行或 `rubric-memo.md` 观察段超过 100 条时，cheatx-status 提示。

## 行数预算（rubric_notes.md）

| 校准池 | 健康 | 警戒 |
|---|---|---|
| 0-14 | 120-220 | > 300 |
| 15-99 | 200-350 | > 450 |
| 100+ | 250-400 | > 500 |

目的：打分前 60 秒内能读完当前规则。

---

## 观察记录模板（rubric-memo.md）

```markdown
### YYYY-MM-DD [短名] (id) — [一句话定性，如"SV 被低估"]
- 形态 / 协变量：thread (7) · 21:00 · 无外链 · 距上一条 95 分钟
- 预测：composite=X.XX，bucket=命中，中枢 N
- 实际：曝光 N（实际/中枢 N.N×）· 互动率 X% · 收藏/赞比 X · 回复 N（T+48h）
- 回复 / 引用要点：[简短摘录 + 赞数]
- 判断：哪个维度被验证 / 推翻？
- 详见：predictions/<file>.md
```

批量复盘时可以合并：

```markdown
### YYYY-MM-DD 批量复盘（5 条）— [一句话共同点]
| id | 形态 | composite | 实际/中枢 | 关键维度 | 备注 |
|---|---|---|---|---|---|
```

跨样本观察模板：

```markdown
### 观察 X — [一句话规律]
**证据**：
- 样本 1（composite, 实际/基线倍数）：要点
- 样本 2 …
**假设**：如果成立，rubric 应该怎么改
样本数：N（默认要求 3）
```

---

## 与 bump 的衔接

`cheatx-bump` Step 5 按顺序处理 `rubric-memo.md` 的观察段：
1. 逐条问：被本次吸收？→ 删。被推翻？→ 删。未解决？→ 迁到"待验证假设"
2. 已验证但不需改公式的规律 → **抽象化**后写进 `rubric_notes.md` 的规律沉淀区，跑 `tools/leak_check.py`
3. 重新读一遍 `rubric_notes.md`，确认 60 秒内能看懂当前规则
