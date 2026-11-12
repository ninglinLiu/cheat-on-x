---
name: cheatx-init
description: cheat-on-x 的首次 onboarding 与脚手架创建器。在用户的 X 内容项目目录里问 8 个问题（账号、形态、语言、每天几条、历史、数据路线、选题池、hooks）+ 对标账号，然后创建状态文件、rubric、目录、模板、hooks，并可导入账号历史建立曝光基线。触发词："初始化 cheat-on-x"/"X 初始化"/"init cheat-on-x"/"setup cheat-on-x"。**其他子 skill 在 .cheatx-state.json 不存在时自动路由到此。**
argument-hint: "[— form: x-post|x-longform|x-mixed]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Skill
---

# /cheatx-init — 首次 onboarding

从零到能写第一条预测：没有历史 ≤ 5 分钟；要导入历史 ≤ 10 分钟。

## Overview

```
Phase 0   检测当前状态
Phase 1   首屏：期望管理
Phase 2   8 个问题（一次一个）
Phase 2.5 对标账号
Phase 3   创建脚手架（逐项解释）
Phase 3.5 导入账号历史（Q5 = 有历史且同意）
Phase 4   测试 hooks 真的生效
Phase 4.5 （Phase 2.5 选 a）进入 /cheatx-learn-from
Phase 5   "下一步说什么"清单
```

## Constants

- **SCHEMA_VERSION = "x1.0"**、**SKILL_VERSION = "0.1.0"**
- **DEFAULT_RETRO_WINDOW_HOURS = 48**、**DEFAULT_RETRO_WINDOW_HOURS_LONGFORM = 168**
- **TREND_DEFAULT_SOURCES = ["manual-paste"]**
- `<cheat-on-x>` = 源码克隆目录：`readlink -f ~/.claude/skills/cheatx-init` 往上两级（Codex：`~/.codex/skills/cheat-on-x`）；找不到就问用户

## Workflow

### Phase 0：检测

1. 当前目录是用户的 **X 内容项目**（不是 cheat-on-x 源码目录——源码目录里有 `install.sh` 和 `skills/cheatx-init/`，是的话提醒用户换目录）
2. 已有 `.cheatx-state.json` → "这个项目已初始化，重新初始化会覆盖配置——确认？"明确确认才继续
3. 有 `.cheat-state.json`（上游 cheat-on-content 的）→ 说明两者不通用：建议在新目录初始化 X 项目
4. 有 `rubric_notes.md` / `predictions/` 但没有 state → 半初始化，问"从现有文件推断，还是重置？"

### Phase 1：首屏（照写，不要软化）

```
🎯 Cheat on X — 初始化

你下一条帖子的表现，有一部分在你写下它之前就决定了。
这套工具让你每条都先下注、再看结果、再修正判断——一条一条地变准。

先说三件事：

1. 前几条预测会很不准。前 5 条中枢误差 ±60% 是正常的，
   工具用 🔴🟠🟡🟢🔵 标 confidence，不藏数字。

2. 预测必须在点"发布"之前写。X 的计数几秒就出来，
   发了再补预测，你一定会被数字影响。

3. 强烈建议导入一个对标账号——15-30 条它的帖子，工具立刻有参照。
   后面会问。

准备好了吗？
```

### Phase 2：8 个问题（一次一个，不批量）

**Q1：账号**

> "你的 X handle 是？现在大概多少粉？有 Premium 吗（没有 / Basic / Premium / Premium+）？"

→ `x_handle`（补 `@`）、`followers_at_init`、`x_premium`（`none` / `basic` / `premium` / `premium_plus` / `unknown`）

**Q2：主要发什么**（可多选）

> "你主要发哪些？
> a) 单条短帖  b) thread  c) 长帖（Premium 长文本）  d) Article
> e) 引用别人的帖子加评论  f) 在别人帖子下回复（回复涨粉）"

→ `forms_enabled`（a→single, b→thread, c→long, d→article, e→quote, f→reply）

`content_form`：
- 只选了 c / d → `x-longform`（起步 rubric：x-longform-zero）
- 没选 c / d → `x-post`（x-post-zero）
- 都有 → `x-mixed`（x-post-zero，长帖按其中的长文条款打）

**Q3：语言**

> "主要用中文、英文，还是都有？"→ `primary_language`：`zh` / `en` / `mixed`

**Q4：节奏**

> "你打算每天发几条主帖（不算回复）？
> a) 1 条  b) 2-3 条  c) 4 条以上  d) 不固定（关闭队列提醒）"

→ `target_posts_per_day`：1 / 3 / 5 / null

**Q5：历史**

> "这个账号发过帖子吗？
> a) 没发过 / 几乎没有
> b) 发过——我可以帮你导入最近的帖子，算出你每种形态的常态曝光（以后预测就有基线了）"

a → `calibration_samples: 0`，跳过 Phase 3.5。
b → 进 Phase 3.5（脚手架建好之后做）。

**Q6：复盘数据怎么拿**

> "发帖 48 小时后复盘，数据从哪来？
>
> a) **油猴脚本导出（推荐，免费）**——装一个浏览器脚本，你在 x.com 上浏览自己主页时点一下导出 CSV。
>    不需要开发者账号，不发额外请求。
> b) X API（按量计费，约 $0.005 / 条帖子读取，一次复盘带 20 条回复约 $0.1）——
>    需要开发者账号和 Bearer Token；每次调用前都会先给你看预估费用。
> c) 手动粘贴——最慢，但什么都不用装。
>
> 不管哪种，复盘都要带上回复（至少 10 条）——只看数字只能告诉你'多少'，回复才能告诉你'为什么'。"

| 答 | `data_collection` | `enabled_perf_adapters` | `x_api` |
|---|---|---|---|
| a（默认） | `csv` | `["x-csv-import"]` | `{"enabled": false, …}` |
| b | `x-api` | `["x-api", "x-csv-import"]` | 问：有没有 token、要不要用户授权、月预算 |
| c | `manual` | `[]` | — |

选 b：token **不进 state**，写进 `.cheatx-secrets.json`（Phase 3 第 0 步先建 .gitignore 再写）或让用户设环境变量。

**Q7：选题池**

> "有现成的选题列表吗？a) 没有（默认） b) 有，markdown c) 有，Notion / 其他"

→ `pool_status`：`none` / `markdown` / `notion`

**Q8：hooks**

> "我装三个 hook，回 yes 就装：
> 1. **预测锁**——预测写完后，你我都改不了预测段，复盘只能往下追加。
>    没这个锁，看到数据后'修一下当时的预测'几乎必然发生。
> 2. **开场报告**——每次开会话自动显示到期复盘、今天发了几条、队列、候选 top 3
> 3. **静默使用日志**——只记事件类型，给 /cheatx-status 统计用
> 回 yes / no。"

→ `hooks_installed`：bool（默认 true）

### Phase 2.5：对标账号

```
🎯 对标账号

找一个你想成为那样的 X 账号（同领域、比你大一两个量级最好），导入它 15-30 条帖子。
工具按它自己的中位数把帖子分成高 / 中 / 低三档，拆出哪些维度和"高"相关。

- 没有历史（Q5=a）→ 强烈建议。不导的话前几条预测基本是占星
- 有历史（Q5=b）→ 可选，建议至少导一个做对照

a) 现在导（脚手架建好后直接进 /cheatx-learn-from）
b) 等下导（state 标 pending，/cheatx-status 会提醒）
c) 不导
```

→ `benchmark_status`：`imported`（a 完成后）/ `pending` / `none`

### Phase 3：创建脚手架（每一项都说明作用）

0. **`.gitignore`（第一步）**

   ```
   先建 .gitignore：挡住 .cheatx-secrets.json（API token）和 imports/（原始导出，里面有别人的回复和 handle，
   还有没到复盘时间的帖子数据）。predictions/ posts/ drafts/ 不挡——预测的不可变档案靠 git history。
   ```
   - 复制 `<cheat-on-x>/templates/gitignore.template`；已有 `.gitignore` → 只追加缺的行（至少 `.cheatx-secrets.json`、`imports/`、`.cheatx-cache/`、`.cheatx-hooks/`）
   - 项目已经 git 跟踪了 imports/ 或 secrets → 提示 `git rm -r --cached imports .cheatx-secrets.json`

1. **`.cheatx-state.json`**——所有 `<…>` 必须换成映射表里的具体值，不存字母：

   ```json
   {
     "schema_version": "x1.0",
     "skill_version": "0.1.0",
     "edition": "x",
     "x_handle": "<Q1>",
     "x_premium": "<Q1>",
     "followers_at_init": <Q1>,
     "primary_language": "<Q3>",
     "content_form": "<Q2 派生>",
     "forms_enabled": [<Q2>],
     "target_posts_per_day": <Q4>,
     "retro_window_hours": 48,
     "retro_window_hours_longform": 168,
     "rubric_version": "v0",
     "benchmark_status": "<Phase 2.5>",
     "benchmark_handles": [],
     "benchmark_sample_count": 0,
     "baseline_impressions": {"all": null, "single": null, "thread": null, "long": null, "article": null, "quote": null, "reply": null},
     "baseline_updated_at": null,
     "calibration_samples": 0,
     "calibration_samples_at_last_bump": 0,
     "data_collection": "<Q6>",
     "enabled_perf_adapters": [<Q6>],
     "x_api": {"enabled": <Q6>, "user_context": <Q6>, "budget_usd_per_month": <Q6 或 null>},
     "pool_status": "<Q7>",
     "data_layer": "markdown",
     "hooks_installed": <Q8 bool>,
     "enabled_trend_sources": ["manual-paste"],
     "last_bump_at": null, "last_bump_self_audited": false,
     "last_published_at": null, "last_published_file": null,
     "last_retro_at": null, "last_trends_run_at": null, "last_trends_added_count": 0,
     "last_prediction_self_scored": false, "last_self_scored_at": null,
     "consecutive_directional_errors": [],
     "pending_retros": [],
     "queue": [],
     "recent_publishes": [],
     "in_progress_session": null,
     "initialized_at": "<本地时区 ISO 8601，如 2026-11-12T20:11:13+08:00；不要用 Z>"
   }
   ```

   `enabled_trend_sources`：AI / 科技账号顺手问一句要不要加 `aihot`；有 MCP 的加 `trendradar-mcp`；用油猴脚本的加 `x-trends`。

2. **`rubric_notes.md`**

   ```
   这是你的评分规则，也是盲打 sub-agent 唯一能读的文件——所以里面只能有通用规则，
   不能有具体帖子和数字（那些写 rubric-memo.md）。
   现在是 v0：7 个正向维度等权 + 1 个负反馈扣分。跑够 5 条复盘后提议第一次升级。
   ```
   - 复制 `templates/rubric_notes.template.md`，把 `[STARTER-RUBRIC]` 换成 `starter-rubrics/x-post-zero.md`（或 `x-longform-zero.md`）全文，`[INIT-DATE]` 换成今天
   - 写完跑 `python <cheat-on-x>/tools/leak_check.py rubric_notes.md`，必须 0

3. **`rubric-memo.md`**：复制 `templates/rubric-memo.template.md`。"带数据的观察和升级记录都在这里，盲打 sub-agent 读不到它。"

4. **`post_patterns.md`**：复制 `templates/post_patterns.template.md`。"rubric 教我怎么打分，这个文件教我怎么写。"

5. **目录**（各加 `.gitkeep`）：

   ```
   drafts/       发帖前的草稿
   predictions/  预测日志（hook 保护）
   posts/        定稿后建：final.md（要发的文本）+ report.md（复盘数据）
   samples/      对标账号样本
   imports/      你导出的 CSV 放这里（不入 git）
   ```

6. **`benchmark.md`**（Phase 2.5 选 a / b）：复制模板

7. **`audience.md`**：复制模板。"读者画像，跑几次复盘后用 /cheatx-persona 从回复里聚出来。它带实际数据，盲打 sub-agent 读不到。"

8. **`WORKFLOW.md`**、**`STATUS.md`**：复制模板，填 `[INIT-DATE]`、handle、Premium、形态

9. **`candidates.md`**（Q7 = b 或想要空池）：复制模板

10. **数据路线**：
    - csv → 告诉用户装油猴脚本：`<cheat-on-x>/userscripts/README.md` 的安装三步；装好后在 x.com 面板里"设置我的 handle"
    - x-api → 引导写 `.cheatx-secrets.json`（`{"x_bearer_token": "…"}`），跑 `python <cheat-on-x>/adapters/perf-data/x-api/xapi.py estimate` 看单价
    - manual → 无

11. **hooks**（Q8 = yes）：
    - 复制 `<cheat-on-x>/hooks/` 下 `prediction-immutability.sh`、`session-start.sh`、`session_start.py`、`log-event.sh` 到 `.cheatx-hooks/`，`chmod +x`
    - 读 `.claude/settings.json`（没有就 `{}`），**合并**（不覆盖已有 hooks）：
      - `hooks/prediction-immutability.json` 的 `PreToolUse`
      - `hooks/session-start.json` 的 `SessionStart`
      - `hooks/meta-logging.json` 的各事件
    - 命令路径统一 `${CLAUDE_PROJECT_DIR}/.cheatx-hooks/...`

### Phase 3.5：导入账号历史（Q5 = b）

目的：算出每种形态的常态曝光（基线），让 cheat-seed 知道你写过什么。**不**为历史帖子造预测文件——它们不是盲预测，造出来只会污染校准池。

1. 拿数据：
   - csv：让用户在 x.com 打开自己主页，往下滚 30-50 条（越多基线越准），面板"导出：我的帖子 + 回复/引用"，放进 `imports/`
   - x-api：`xapi.py history <handle> --limit 50 --project .` 先预演给费用，同意后 `--yes`
   - manual：问"最近 10 条大概多少浏览？"——给个范围就行
2. 跑：
   ```bash
   python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py history imports/<file>.csv --handle <handle> --project . --samples-dir samples/<handle>
   ```
3. 写 state：`baseline_impressions` ← 输出的 `median_by_form`（样本 < 3 的形态留 null）+ `all` ← `median_impressions`；`baseline_updated_at`
4. 写 `rubric-memo.md` 的"基线 / bucket 重算记录"一行（来源：历史导入，N 条）
5. 告诉用户："导入了 N 条。你的常态：单帖中位数 X、thread 中位数 Y。高档（≥2× 中位数）的 K 条在 samples/<handle>/，以后 /cheatx-seed 会参考它们。"
6. `calibration_samples` 保持 0——历史不是校准样本

失败（导出没有你的帖子 / API 报错）→ 降级为 manual 估值，不阻塞。

### Phase 4：测试 hooks（Q8 = yes）

**不假装成功。**两步都要做：

1. **脚本直测**：

   ```bash
   mkdir -p predictions
   printf '# t\n\n## 预测 v1\n\nBucket: 命中\n\n## 复盘\n' > predictions/_hooktest.md
   printf '{"tool_name":"Edit","tool_input":{"file_path":"predictions/_hooktest.md","old_string":"Bucket: 命中","new_string":"Bucket: 大爆"}}' \
     | bash .cheatx-hooks/prediction-immutability.sh; echo "exit=$?"
   ```
   期望 `exit=2`（Claude Code 只在退出码 2 时拦截工具调用）。

2. **真实拦截**：用 Edit 工具试改 `predictions/_hooktest.md` 的 `Bucket: 命中` → 期望被 hook 拒绝。

   注意：`.claude/settings.json` 新加的 hooks 可能要**重启 Claude Code 会话**才生效。第 2 步没被拦 → 告诉用户"脚本是好的，但这个会话还没加载新 hook，重开一个会话后再试一次"。

3. 删除 `predictions/_hooktest.md`
4. 开场报告：`bash .cheatx-hooks/session-start.sh` 应输出几行报告

任何一步失败 → 明确告诉用户哪一步、可能原因（没装 jq 和 python / settings.json 没生效 / 需要重启），**不写"✅ 初始化完成"**。

### Phase 4.5：对标导入（Phase 2.5 = a）

```
✅ 脚手架和 hooks 装好了。现在直接进 /cheatx-learn-from 导入对标账号。
```

调 `/cheatx-learn-from`，完成后回到 Phase 5。

### Phase 5：下一步清单

```
✅ 初始化完成 · rubric v0 · 校准样本 0 · confidence 🔴

以后直接说：
📝 写好草稿     → "打分这条 drafts/<…>.md"（探索，不写文件）
🎯 发之前       → "启动预测 drafts/<…>.md" / "快押 …" / "批量预测 drafts/"
📦 定稿         → "定稿 drafts/<…>.md"
🚀 发完         → "已发 https://x.com/…/status/…"
📊 48 小时后    → 油猴脚本导出 → "复盘到期的 imports/<…>.csv"
📈 任何时候     → "X 状态"

<Q7 = a：>
🌱 现在跑 /cheatx-seed 找第一批选题？回 "yes" 立刻开始。

💡 confidence 会随复盘自动提升：第 5 条复盘 🟡，第 15 条 🟢。
   别因为 confidence 低就跳过预测——早期预测的价值是采集数据，不是做决策。
```

## Key Rules

1. 不假装成功：哪一步失败就说哪一步
2. 一次只问一个问题
3. 每创建一个文件都说明它干什么
4. state 只存映射后的值，不存字母；bool 存 bool
5. token 绝不进 state、绝不进 git
6. 历史导入不造预测文件、不加校准样本

## Refusals

- 「跳过问题，直接建文件」 → 拒绝。答案决定 rubric、节奏、hooks
- 「把我另一个项目的配置同步过来」 → 提示手动复制 `.cheatx-state.json` 和 `rubric_notes.md`，不自动跨项目同步
- 「不装 hook 但保留 immutability」 → 允许，`hooks_installed: false`，cheatx-status 持续提示"预测锁是君子协定"
- 「把我历史帖子都补成预测」 → 拒绝。看过结果的预测不是预测；需要的话逐条 `_redo` reconstructed，且不进校准池

## State 字段写入清单

| 字段 | 时机 | 来源 |
|---|---|---|
| `schema_version` / `skill_version` / `edition` | Phase 3 | 常量 |
| `x_handle` / `x_premium` / `followers_at_init` | Phase 3 | Q1 |
| `forms_enabled` / `content_form` | Phase 3 | Q2 |
| `primary_language` | Phase 3 | Q3 |
| `target_posts_per_day` | Phase 3 | Q4 |
| `retro_window_hours*` | Phase 3 | 常量 |
| `data_collection` / `enabled_perf_adapters` / `x_api` | Phase 3 | Q6 |
| `pool_status` | Phase 3 | Q7 |
| `hooks_installed` | Phase 3-4 | Q8 |
| `benchmark_*` | Phase 3 / learn-from | Phase 2.5 |
| `baseline_impressions` / `baseline_updated_at` | Phase 3.5 | 历史导入 |
| 其余 | Phase 3 | 初值 |
