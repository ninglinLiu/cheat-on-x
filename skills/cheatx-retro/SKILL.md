---
name: cheatx-retro
description: T+48h（长帖 / Article T+7d）数据回收 + 复盘：拿到实际数据 → 对照预测 → 提炼观察写进 rubric-memo.md → 重算该形态基线 → 判断要不要提议 bump。支持单条和批量（"复盘到期的 <csv>" 一次处理所有到期帖子）。数据来源：油猴脚本 / X Analytics 导出的 CSV（默认）、X API（可选）、手动粘贴。只追加 `## 复盘` 段，绝不改预测段。触发词："复盘 [path]"/"复盘到期的 [csv]"/"retro"/"48 小时到了"/"把这几条复盘了"。
argument-hint: '<prediction-file | posts/<id>/ | due> [<csv>...] [— source: csv|x-api|manual] [— early]'
allowed-tools: Bash(*), Read, Edit, Write, Glob, Grep, Skill
---

# /cheatx-retro — 数据回收与复盘

拿实际表现 → 对照预测 → 提炼观察 → 写入 `rubric-memo.md`。**只追加 `## 复盘` 段，绝不改预测段**。

`rubric_notes.md` 是 blind 白名单：复盘**不往里写任何东西**。样本名、数字、回复、链接全部进 `rubric-memo.md`。

## Overview

```
[复盘 predictions/… | 复盘到期的 imports/x.csv]
  ↓
Phase 0 校验：预测段 cache、已登记发布、窗口到了没
Phase 1 取数：csv（默认）/ x-api / manual → posts/<id>/report.md
Phase 2 实际数据 + 派生比率 + log score + 外生冲击判断
Phase 3 回复与引用聚类
Phase 4 验证 / 推翻
Phase 5 新观察（rubric-memo / post_patterns）
Phase 6 追加 ## 复盘 段 + 哈希复核
Phase 7 写 rubric-memo.md（+ 用户确认后写 post_patterns.md）
Phase 8 重算基线 + 偏差累计 + 是否提议 bump + state
```

## Constants

- **RETRO_WINDOW_HOURS** = `state.retro_window_hours`（默认 48）；`long` / `article` 用 `retro_window_hours_longform`（默认 168）
- **MIN_REPLIES = 10**——回复样本低于这个数，复盘照做但"回复与引用"一节标"样本不足"
- **ON_TARGET_BAND = 0.5 – 2×**（实际 / 中枢）；**EXTREME** = ≤ 0.2× 或 ≥ 5×
- **AUTO_PROPOSE_BUMP = true**——判断规则见 Phase 8

## Inputs

| 形态 | 处理 |
|---|---|
| `predictions/<…>.md` | 单条 |
| `posts/<…>/` | 按同名找预测文件 |
| `due` / `复盘到期的` + CSV 文件 | 批量：`state.pending_retros` 里所有 `due_at` 已过的 |
| 缺省 | 列出到期的，问用户要哪条、数据从哪来 |

## Workflow

### Phase 0：校验（每条）

1. 预测文件存在；识别所有 `## 预测…` 段，**最后一个 `## 预测 vN` 是有效预测**
2. **在内存里 cache 锁定区**——第一个 `## ` 标题到 `## 复盘` 之前的全部内容（Phase 6 复核用）
3. header 有 `Published at` 和 `Status ID` → 没有就提示先 `/cheatx-publish`
4. 窗口：现在 − 发布时间 ≥ 对应窗口？
   - 不够 → "还差 N 小时。坚持现在复盘会标 `early_retro: true`，bump 时权重减半"
5. 已有复盘内容 → 问"补充还是修正？"（补充：追加带日期的子段；修正预测段：拒绝）
6. header 有 `Reconstructed retrospective` → 可以复盘，但**不计入** calibration_samples

### Phase 1：取数

`state.data_collection` 决定默认路线；用户可以 `— source:` 覆盖。

#### Route A：CSV（默认）

用户在 x.com 用油猴脚本导出（或 X Analytics 导出）放进 `imports/`。还没导出就先给步骤：

```
1. 在 x.com 打开你的主页，往下滚过要复盘的这几条
2. 想要回复：点进每条帖子，把回复区滚一遍（每条至少要 10 条回复才有分析价值）
3. 可选：帖子 → 查看帖子分析 → 面板"读取本页分析数据（实验）"——补主页访问 / 新增关注
4. 面板点"导出：我的帖子 + 回复/引用"，文件放进 imports/
```

批量：

```bash
python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py due imports/<file>.csv [更多文件…] --project . --label csv:userscript
```

单条：

```bash
python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py post imports/<file>.csv \
  --id <status_id> --out posts/<…>/ --published-at <Published at> --final posts/<…>/final.md \
  --window-hours 48 --form <form> --label csv:userscript
```

- 第一次用某个非油猴导出的文件 → 先 `inspect` 看列映射，必要时 `--map`
- 输出 JSON 里 `found: false` → 告诉用户哪条没在导出里，怎么补
- `early_snapshot: true` → 快照早于窗口，复盘段注明
- 导入器只打印**到期**帖子的数字——不要自己打开 CSV 去读其他行

`<cheat-on-x>` 是源码克隆位置：`readlink -f ~/.claude/skills/cheatx-retro` 往上两级；找不到就问用户。

#### Route B：X API（可选）

```bash
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py due --project . --replies 20         # 预演：看费用
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py due --project . --replies 20 --yes   # 用户确认后
```

**先跑预演，把预估费用告诉用户，用户同意才加 `--yes`。**`state.x_api.budget_usd_per_month` 有值时，超预算先问。API 拿不到新增关注，回复只覆盖近 7 天。

#### Route C：手动粘贴

请用户粘：曝光、赞、转发、引用、回复数、收藏（有的话：主页访问、新增关注、链接点击），以及**至少 10 条回复（带赞数）**。写成 `posts/<…>/report.md`（格式同导入器输出），`数据来源: manual paste`。

用户拒绝给回复或少于 5 条 → 先问原因。确实拿不到（回复关闭 / 太少）→ 标 `replies_unavailable`，复盘价值打折，但继续。

#### 任何路线失败

CSV 里没有这条 / API 报错 / 限流 → 告诉用户原因，降级到下一条路线。**不阻塞**。

### Phase 2：实际数据

从 report.md 读数字，写进复盘段（格式见 [templates/retro.template.md](../../templates/retro.template.md)）：

- 曝光 → 落在哪个 bucket（用预测 header 的 Baseline 换算）；**实际 / 中枢**
- **实际 bucket 的预测概率** + log score（`ln(p)`）——长期平均 log score 是概率校准的指标
- 赞 / 转 / 引用 / 回复 / 收藏；有就写主页访问、新增关注、链接点击
- 派生比率（导入器已算好）：互动率、收藏/赞比、回复率、转引率、主页访问率、每千曝光新增关注
- 次要押注逐项 ✅ / ❌
- **外生冲击判断**：回复 / 引用里出现粉丝量级远大于你的账号的转发或引用、或用户说"被 @xxx 转了"、或曝光是同形态基线的 10× 以上且转引率异常 → 问用户确认。确认 → 标 `exogenous_boost`，这条**不计入**连续偏差，bump 时排除
- 发出文本一致性：header 里 `Posted Text Check` 是 `unchecked` 且 report.md 有发出正文 → 现在用 `tools/posted_text_check.py` 补查；≥ 30% → Integrity warning

### Phase 3：回复与引用

从 report.md 的回复 / 引用列表聚类成 3-5 类，例如：

| 类别 | 对应维度 |
|---|---|
| 补充（"还可以加……"） | RP 的健康形态 |
| 求资源 / 求模板 | SV |
| 共鸣 / 身份认同（"说的就是我"） | RS |
| 反对 / 纠错 | RP（可能也是 NR） |
| @朋友 | SV（私信 / 转发给具体的人） |
| 问"你是做什么的" | FT |
| 离题 / 刷屏 | NR 信号 |

每类：条数占比 + 一条代表性回复（带赞数，**不写回复者 handle**）。

### Phase 4：验证 / 推翻

逐项对照预测文件：
- 推理因素表：每个"高置信度"因素被验证还是推翻
- 反事实：实际落中的那个场景，它写的"意味着什么"成立吗
- 关键校准假设：算实际倍数比，和押的比
- 中枢偏差：实际 / 中枢 落在 0.5–2× 之外就明写

每条引用具体数字。不许写"基本符合"。

### Phase 5：新观察

#### 5a rubric 观察（→ rubric-memo.md）

维度 / 权重 / bucket / 协变量相关，每条可追溯到数据点。例：
- "SV=5 的两条清单 thread 实际 / 中枢都 ≥ 2.5×，收藏/赞比 > 0.5——SV 可能被低估"
- "距上一条 < 60 分钟的三条全部落在持平以下"（协变量信号，不是维度信号）

#### 5b 写法观察（→ post_patterns.md，**用户确认后才写**）

对比 `drafts/<id>.md` → `posts/<id>/final.md` → 实际发出正文：用户改了什么、效果如何。新 pattern 标"单样本待验证"。

问用户："要把这些追加到 post_patterns.md 吗？（全部 / 选几条 / 不要）"

### Phase 6：追加复盘段

用 Edit，在 `## 复盘` 下追加（有占位"（待填……）"先删掉占位行）。批量时每条各自 Edit 自己的文件。

**写完立刻复核**：重新读文件，锁定区内容必须和 Phase 0 的 cache 逐字相同。不等 → 报错、回滚这次编辑、告诉用户。

### Phase 7：写 rubric-memo.md

按 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 的模板追加到 `rubric-memo.md` 的 `## 观察记录`。批量复盘可以合成一张表。

然后扫已有观察：新观察和已有观察是否构成同一 pattern ≥ 3 条（外生 / integrity 样本不算）→ 升格到 `## 重大跨样本观察`。

**不写 `rubric_notes.md`**。规律要等 `/cheatx-bump` 落地时抽象化后才进去。

### Phase 8：基线、偏差、bump 提议、state

1. **重算基线**：

   ```bash
   python <cheat-on-x>/tools/calib_pool.py baseline predictions/ --json
   ```

   输出每个形态最近 10 条已复盘样本的曝光中位数（排除 reconstructed / integrity / exogenous）。写回 `state.baseline_impressions` + `baseline_updated_at`；变化超过 30% 的形态，在 `rubric-memo.md` 的"基线 / bucket 重算记录"追加一行。

2. **偏差方向**（外生样本跳过）：
   - 实际 / 中枢 < 0.5 → push `{"dir": "high", "ratio": …, "file": …}`
   - > 2 → push `{"dir": "low", …}`
   - 0.5–2 → 不 push；**并清空**累计（连续性被打断）

3. **是否提议 bump**（Claude 判断，默认参考）：
   - 连续 ≥ 4 次同向 → 提议
   - 1 次极端（≤ 0.2× 或 ≥ 5×）且不是外生、能解释为某个维度漏判 → 提议
   - 同向但每次都只是略出带外 → 先查协变量（时段 / 间隔 / Premium / 外链），可能不是 rubric 的问题
   - 偏差跨多个维度、没有清晰方向 → 不提议

   ```
   🚨 [连续 4 次低估 / 1 次 8× 极端低估]
   可能是 rubric 系统性偏差。建议跑 /cheatx-bump，或先 /cheatx-status 看详情。
   本次提议是 default-aligned / judgment-driven。
   ```

4. **state**：
   ```json
   {
     "calibration_samples": "+1（reconstructed 不加）",
     "pending_retros": "[移除本条]",
     "last_retro_at": "<ISO>",
     "consecutive_directional_errors": "[…]",
     "baseline_impressions": "{…}",
     "baseline_updated_at": "<ISO>"
   }
   ```

5. 批量结束输出一张总表：

   ```
   | 帖子 | 形态 | 预测 | 实际 | 实际/中枢 | log score | 备注 |
   ```

   + 累计校准样本、当前 confidence、平均 log score（最近 20 条）、是否提议 bump。

## Key Rules

1. 预测段 immutable：Phase 0 cache + Phase 6 复核双保险
2. 数据来源必须写明（`csv:userscript（文件名）` / `x-api` / `manual paste`）
3. 每条观察可追溯到数字
4. 复盘里不 bump——只提议，执行走 `/cheatx-bump`
5. 早复盘标 `early_retro: true`
6. 不往 `rubric_notes.md` 写任何东西
7. report.md 不写回复者 handle

## Refusals

- 「把预测段的概率改一下让复盘好看点」 → 拒绝
- 「跳过观察提炼」 → 拒绝。观察是 rubric 进化的唯一燃料
- 「不要回复了，只看数字」 → 先劝；坚持则标 `replies_unavailable`，复盘价值打折
- 「顺便把还没到期的那几条也看一眼」 → 拒绝。它们的窗口没到，看了就不盲——除非用户明确要 `— early` 并接受降权
- 「直接 bump」 → 拒绝，走 `/cheatx-bump`

## Integration

- 前置：`/cheatx-publish` 已登记 + 窗口已到
- 下游：偏差累计 → `/cheatx-bump`；回复积累 → `/cheatx-persona`
- 与 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 紧耦合
