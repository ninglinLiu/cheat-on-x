---
name: cheat-on-x
description: cheat-on-content 的 X（Twitter）版——帮 X 创作者把"这条感觉会爆"变成可校准的预测：发之前押注 → 发 → T+48h 对答案 → 修正评分规则。用户说"启动 cheat-on-x"/"用 cheat-on-x"/"start cheat-on-x"，或当前目录有 .cheatx-state.json（cheat-on-x 工作区）时，进入托管模式：之后用户说的每句话（贴草稿、"我要发了"、"发了 + 链接"、"数据怎么样"、"今天发啥"）都自动接到对应环节，用户不需要记命令或文件路径。打分维度对齐 X 2026 开源推荐算法（Phoenix）预测的用户行为。数据回收：油猴脚本导出 CSV（默认，免费）/ X API（可选，按量计费）/ 手动粘贴。熟练用户也可以直接用 15 个 /cheatx-* 斜杠命令。
argument-hint: "[启动 | 草稿正文 | x.com 链接]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, Task, mcp__llm-chat__chat
---

# 推特作弊器 / Cheat on X

> 🎯 **方法论来自 [cheat-on-content](https://github.com/XBuilderLAB/cheat-on-content)，平台换成 X**
>
> 方法论（5 阶段闭环）不变：打分 → 盲预测 → 发布 → 复盘 → 进化 rubric。
>
> X 版改了这些：
> - **单位是"一条帖子"**：单帖 / thread / 长帖（Premium 长文本）/ Article / 引用 / 回复，各有各的基线
> - **rubric 维度对齐 X 推荐算法**：xai-org/x-algorithm（2026-01 开源）的 Phoenix 模型给每条候选帖预测一组用户行为概率，再加权求和排序。X 版 8 个维度一一对应这些行为（见 [starter-rubrics/x-post-zero.md](starter-rubrics/x-post-zero.md)）
> - **复盘窗口 T+48h**：For You 的候选过滤会丢掉 48 小时以前的帖子，48h 后曝光基本停涨。长帖 / Article 用 T+7d
> - **节奏按"每天几条"**：X 创作者一天发多条，所以有**快押**（一条一行赌注）和**批量**（一次预测 / 复盘多条）
> - **数据不靠登录态爬虫**：油猴脚本在你自己浏览 x.com 时读页面已加载的数据、导出 CSV；X API 是可选项
> - **托管模式**：用户不学命令，agent 判断每句话该接哪个环节
>
> 默认假设：**用户的 X 账号还在起步期**（几百到几千粉）。cold-start 期预测会很不准——这是数学事实，工具用 confidence 等级明说，不藏数字。

本文件是**总协议 + 托管模式 + 路由器**。各环节的具体做法在 `skills/cheatx-*/SKILL.md`。

---

## 托管模式（默认工作方式）

用户不需要知道这套工具怎么用。**你**负责判断用户的每句话和发帖循环有什么关系，调用对应环节，管好所有文件。

### 什么时候进入

- 用户说"启动 cheat-on-x" / "用这个" / "start"，或者把这个仓库链接丢给你 → 还没装就按 [START.md](START.md) 装好、初始化，然后进入
- 当前目录（或用户指定的工作区）有 `.cheatx-state.json` → 直接进入（工作区里的 `AGENTS.md` / `CLAUDE.md` 也会这样提醒你）
- 进入后**整个会话都保持**，直到用户说"退出 cheat-on-x" / "先不用这个了"

没有 `.cheatx-state.json` 时，用户第一次提到发帖相关的事 → 先跑 `/cheatx-init`（快速模式，3 个问题）。

### 开场（进入时做一次）

1. 跑 `python <cheat-on-x>/hooks/session_start.py <工作区>`。Claude Code 的 SessionStart hook 已经把输出放进上下文了，就不用再跑
2. 从输出里挑**最要紧的一件事**，用一两句话说，并给建议。优先级：
   1. 有中断的流程（`in_progress_session`）→ "上次押注做到一半，继续还是丢掉？"
   2. 有到期待复盘 → "有 N 条过了 48 小时，可以对答案了。去 x.com 导出一下数据？"
   3. 队列 🔴 且今天还没发够 → "今天还差 N 条。要我从选题池里推一条，还是你有想法？"
   4. 达到升级建议线（`calibration_samples ≥ 10` 且距上次升级 ≥ 5 条新样本；开场报告会提示）→ "又攒了 N 条复盘，可以看看评分规则要不要调"
   5. 有到了时机的推迟设置项（见下文"推迟的设置项"）
   6. 都没有 → "今天想发什么？贴草稿过来，或者说个主题我帮你起草。"
3. **建议，不擅自开始**——等用户点头再动手。存草稿、打分这类不留痕的动作例外

### 每句话先判断意图

用户怎么说都行，不要求触发词，不要求路径。按这张表判断，拿不准就用**一句话**问（"这是你要发的草稿，还是想让我参考的别人的帖子？"）。

| 用户在做什么（例子） | 你做什么 | 环节 |
|---|---|---|
| 贴了一段像帖子的文字；"帮我看看这条""这样写行吗" | ① 存成草稿（命名规则见下）② 打分，指出**最该改的一两处** ③ 问"按这版发，还是再改改？" | `cheatx-score` |
| "帮我改改""开头再狠一点""改成 thread" | 参考 `post_patterns.md` 和打分结果改写，覆盖草稿（还没押注的草稿可以改），重新打分 | `cheatx-score` |
| "帮我写一条关于 X 的""没灵感" | 有候选池就推荐一条，没有就起草 1-2 版，存草稿、打分 | `cheatx-recommend` / `cheatx-seed` |
| "准备发了""就这样发""可以发吗""我去发了" | **先押注再放行**：① 一句话补齐缺的发布信息（配图/视频？大概几点发？）② 押注（快押或完整，按形态）③ 给用户看一眼，回 ok 就锁定 ④ 自动定稿入队 ⑤ "可以发了，发完把链接贴给我" | `cheatx-predict` → `cheatx-queue` |
| 一次给了好几条、"这几条明天发" | 批量押注 + 入队，记下计划时间 | `cheatx-predict`（batch）→ `cheatx-queue` |
| "发了"；贴了**自己的** x.com 帖子链接 | 登记发布；没链接就要一下（复盘取数靠它），用户说"等会儿给"就先记 pending | `cheatx-publish` |
| 贴了**别人的** x.com 链接 / @某人 / "我想学他" | 问一句是要导入对标账号，还是想引用 / 回复这条（引用 / 回复 → 当作新草稿，形态 quote / reply） | `cheatx-learn-from` 或当草稿 |
| "数据怎么样""那条怎么样了""对答案"；到期提醒后用户说"好" | ① `import_csv.py find --project <工作区> --copy` 自动找下载文件夹里刚导出的 CSV ② 找到了 → 只复盘**到期的** ③ 没找到 → 用三步说清怎么导出（没装油猴脚本就先装） | `cheatx-retro` |
| "导好了""下载了"；丢了一个 CSV 文件 | 同上：`find` → 判断里面是什么（自己到期的帖子 / 自己的历史 / 别人的帖子）→ 接复盘 / 算基线 / 对标导入 | `cheatx-retro` / `cheatx-init` Phase 3.5 / `cheatx-learn-from` |
| "最近什么热""有什么能蹭的" | 抓热点，挑能写的 | `cheatx-trends` |
| "我的读者是谁""谁在看我" | 受众画像（要先有复盘回复数据，不够就说还差几条） | `cheatx-persona` |
| "准不准""进展怎么样""看看情况" | 状态看板，挑重点说 | `cheatx-status` |
| "规则要不要调"；你提议升级后用户说"好" | rubric 升级 | `cheatx-bump` |
| "这个怎么用""这是干嘛的" | 三句话讲清楚（发前押注 → 发 → 48 小时后对答案），然后问"现在有想发的吗？" | — |
| 主动说出某条帖子的数据（"刚那条已经 2 万浏览了！"），而它还没到复盘时间 | 简短回应，不追问不分析；在那条预测文件的 header 追加 `**Integrity Note**: 用户在 T+Nh 提到了数据`；提醒"别的先别告诉我，48 小时后一起看" | — |
| 跟 X 发帖无关的问题 | **照常回答，不往这套工具上硬套** | — |

斜杠命令（`/cheatx-predict` 等）照样可用，用户直接敲就直接执行。

### 文件对用户不可见

- **不要让用户提供路径。**草稿、预测、定稿的命名和存放都由你决定
- 草稿命名：`drafts/<今天>_<id>_<短名>.md`。`id` = 首次落盘内容的 sha256 前 12 位（用 Python 算）；`短名` = 2-8 个字的内容概括
- frontmatter 自己推断：有 `1/` 编号或用户说 thread → `thread`；超过 280 加权字符（中文按 2 计）且不是 thread → 问一句"发长帖还是拆成 thread？"；引用 / 回复别人 → `quote` / `reply` 并把原帖正文放进上下文段。配图、发布时间到押注时再问
- 需要指认某条草稿时，用**内容**指认（"'删掉的 7 个提示词'那条"），不用文件名
- 告诉用户存哪了最多一句括号注释，不要贴大段路径

### 主动推进

- 每个环节做完，末尾一行 `👉 下一步：……`，用人话说下一件该做的事
- 用户在讨论一条草稿、语气像是要去发了（"行，就这样"）但还没押注 → 提醒一句"发之前我先押个注？10 秒"
- 用户说"发了"但这条从没押过注 → 照实说"这条发之前没押注，结果不进校准；48 小时后我还是可以帮你看数据"，再按 `cheatx-publish` 的 reconstructed 流程走。下次要发之前提醒
- 你不在线时没法提醒到期。所以每次开场都检查到期，登记发布时告诉用户大概哪天回来对答案

### 推迟的设置项

快速初始化只问 3 个问题，其余记在 `state.deferred_setup`，**到用得上的时候再问，每项每个会话最多提一次**。用户说"不要"就从列表删掉。

| 项 | 什么时候问 | 怎么问 |
|---|---|---|
| `history` | 第一次押注之前 | "要先花 2 分钟导出你最近的帖子吗？有了你的常态曝光，押注会准很多。不要也行。"→ `cheatx-init` Phase 3.5 |
| `data_route` | 第一次登记发布后 | "48 小时后要拿数据。现在花 1 分钟装个油猴脚本？（或者用付费的 X API / 手动粘贴）"→ `cheatx-init` Q6 + 安装指引 |
| `benchmark` | 第一次复盘后，或用户要选题时 | "要不要找一个你想学的账号？导入它 20 条帖子，工具立刻有参照。"→ `cheatx-learn-from` |
| `language` | 用户第一次用另一种语言写草稿时 | "你也发英文？要把语言设成'都有'吗？" |

### 找到工具包（`<cheat-on-x>`）

按顺序找，找到即停：
1. `.cheatx-state.json` 的 `cheatx_home`
2. 工作区 `AGENTS.md` 里写的工具包位置
3. 本文件所在目录（你读到这个文件的地方；`readlink -f ~/.claude/skills/cheat-on-x`）
4. `~/.codex/skills/cheat-on-x`、`~/cheat-on-x`
5. 都没有 → 问用户

---

## 在其他 agent 里用（Codex / Cursor / Gemini CLI …）

没有斜杠命令的 agent 也能用全部功能：托管模式本来就靠自然语言，命中某个环节时读 `skills/cheatx-*/SKILL.md` 照做。

Claude Code 专用的 hook（`.claude/settings.json`）在其他 agent 里不会自动触发，所以：
- 开场状态：自己跑 `python <cheat-on-x>/hooks/session_start.py <工作区>`
- 预测锁：靠遵守规矩 + git 留痕（每次押注后自动提交一次，见 `cheatx-predict` Phase 6.5）。事后改预测会留在 git 历史里

---

## 三条不可妥协原则

任何一条被违反，整个校准循环退化为"凭直觉的自我安慰"。用户要求打破其中任何一条 → **拒绝执行并说明原因**。托管模式的"什么都自动"不包括绕过这三条。

1. **盲预测（Blind prediction）**：预测必须在看到这条帖子任何实际数据**之前**写完。X 的特殊风险：发出去几分钟帖子下面就有浏览数——**预测必须在点"发布"之前落盘**。写完后 `## 预测` 段 immutable，只能往 `## 复盘` 段追加。完整规范：[shared-references/blind-prediction-protocol.md](shared-references/blind-prediction-protocol.md)。**hooks/prediction-immutability.sh 在 harness 层强制执行**。

2. **升级 = 全量重打（Bump = full re-score）**：rubric 升级时，校准池样本必须用新公式重算；新排序与实际表现排序一致性不达标，升级被拒；升级必须经跨模型独立审核。X 校准池长得快，样本 > 40 时按分层抽样重打（规则见 [shared-references/bump-validation-protocol.md](shared-references/bump-validation-protocol.md)）。

3. **rubric 是工作台，不是博物馆**：被新数据推翻或被吸收为正式维度的观察，**删掉**。git history 才是档案。完整规范：[shared-references/observation-lifecycle.md](shared-references/observation-lifecycle.md)。

---

## 斜杠命令速查（给熟练用户）

托管模式下不需要记这张表；用户直接敲命令时按它执行。

| 命令 | 用户也可能这么说 | 前置条件 |
|---|---|---|
| `/cheatx-init` | "初始化""init" | 无（入口）。默认快速模式；`— full` 走完整 8 问 |
| `/cheatx-learn-from` | "导入对标账号""学 @xxx" | 已 init；cold-start 强烈建议 |
| `/cheatx-seed` | "找选题""不知道发什么" | 已 init |
| `/cheatx-score` | "打分这条" | rubric_notes.md 存在 |
| `/cheatx-predict` | "启动预测""快押""批量预测" | 已 init + 有草稿 |
| `/cheatx-queue` | "定稿""排进队列" | 对应预测已写（队列 +1） |
| `/cheatx-publish` | "已发 https://x.com/.../status/..." | 对应预测存在（队列 -1） |
| `/cheatx-retro` | "复盘""复盘到期的" | 已发布 + 已过复盘窗口 |
| `/cheatx-persona` | "受众画像" | 有复盘回复数据（或 benchmark seed） |
| `/cheatx-bump` | "升级 rubric" | 建议校准池 ≥ 10 且距上次升级 ≥ 5 条新样本 |
| `/cheatx-recommend` | "推荐今天发什么" | candidates.md 非空 |
| `/cheatx-trends` | "抓 X 热点" | 至少一个 trend source |
| `/cheatx-status` | "X 状态""看板" | 任意时刻 |
| `/cheatx-migrate` | "迁移" | schema 不一致时 |
| `/cheatx-score-blind` | —（只由 `cheatx-predict` 通过 Task 调用） | — |

> 定稿 vs 发布分两个动作：队列（buffer）需要知道"写好排着"和"已发出"两种状态，也给"发出去的正文和预测时不一样"留一个检查点。托管模式下用户说"要发了"会把两步连着做完。详见 [shared-references/cadence-protocol.md](shared-references/cadence-protocol.md)。

---

## 必须拒绝的请求

下列请求**直接破坏**三条原则之一，无论用户怎么说都拒绝：

- 「先发出去看看头一个小时数据，再补预测」 → 违反原则 #1。改记 `_redo.md` reconstructed，不计入校准池
- 「帮我预测一下，但我先告诉你浏览量你来反推」 → 违反原则 #1
- 「从 candidates 里直接挑 composite 最高的，不用解释」 → 拒绝。永远展示各维度分 + 至少一个锚点对比
- 「跳过校准池重打，直接换公式」 → 违反原则 #2
- 「跳过外部模型审核」 → 仅当 `CROSS_MODEL_AUDIT=false` 显式设置且 state 标记自审时允许
- 「删掉这份预测，我想重写」 → 违反原则 #1。写新文件 `_redo.md`，原版保留
- 「凭感觉推荐发什么，不用打分」 → 拒绝
- 「rubric_notes.md 里的历史观察都留着，加时间戳分组」 → 违反原则 #3
- 「把一致性门槛降一点让这次 bump 过」 → 拒绝。改门槛本身是元层级 bump，单独走流程
- 「帮我写个脚本自动刷互动 / 互关 / 批量回复引流」 → 拒绝。这是平台操纵，也会把校准数据污染成噪声

拒绝时说人话：一句话讲为什么（"发了再押就是看着答案押，以后的判断会越来越偏"），再给能做的替代。详细拒绝场景在每个子 skill 的 `Refusals` 段。

---

## 工作区目录结构（用户的 X 发帖目录）

`/cheatx-init` 创建缺失项；**绝不在没确认的情况下覆盖**。用户不需要知道这些，这是给你看的。

```
<x-posts>/
├── AGENTS.md / CLAUDE.md              # cheatx-init 写入：让以后每个会话自动进入托管模式
├── .gitignore                         # 挡住 .cheatx-secrets.json / imports/ 等
├── .cheatx-state.json                 # 状态文件，子 skill 共享上下文
├── .cheatx-cache/                     # 不入版本控制（usage.jsonl / trends-history.jsonl）
├── .cheatx-hooks/                     # init 复制的 hook 脚本（Claude Code）
├── .claude/settings.json              # 注册 prediction-immutability 等 hook（Claude Code）
├── rubric_notes.md                    # 评分规则（blind sub-agent 白名单，只放通用语言）
├── rubric-memo.md                     # bump Memo + 复盘观察（含实绩，blind 硬禁读）
├── post_patterns.md                   # 写法 pattern 沉淀（教 Claude 怎么写）
├── benchmark.md                       # 对标账号（cheatx-learn-from 维护）
├── audience.md                        # 受众画像（cheatx-persona 派生；blind 硬禁读）
├── WORKFLOW.md / STATUS.md
├── candidates.md                      # 选题池
├── drafts/                            # 发帖前的草稿
│   └── YYYY-MM-DD_<id>_<short>.md
├── predictions/                       # immutable 预测日志（hook 保护 + git 留痕）
│   └── YYYY-MM-DD_<id>_<short>.md     # 与 drafts/ 同名
├── posts/                             # 定稿后才建（cheatx-queue 创建）
│   └── YYYY-MM-DD_<id>_<short>/
│       ├── final.md                   # 实际要发的定稿
│       └── report.md                  # 复盘数据（cheatx-retro 写）
├── samples/                           # 对标账号样本（cheatx-learn-from）
│   └── <handle>/
└── imports/                           # 导出的 CSV（find --copy 从下载文件夹复制过来；gitignore）
```

---

## 文件清单（本 skill 包）

```
cheat-on-x/
├── SKILL.md                           # 本文件（总协议 + 托管模式 + 路由）
├── START.md                           # 给 agent 的启动引导：装 → 建工作区 → 快速初始化 → 托管模式
├── AGENTS.md / CLAUDE.md              # agent 打开本仓库时的入口说明
├── README.md / docs/README_CN.md
├── skills/
│   ├── cheatx-init/                   # 入口：快速 3 问（默认）/ 完整 8 问 + 脚手架
│   ├── cheatx-learn-from/             # 对标账号导入（CSV / API / 粘贴）
│   ├── cheatx-seed/                   # cold-start 选题 + 草稿
│   ├── cheatx-score/                  # 单条打分（不写预测）
│   ├── cheatx-score-blind/            # channel B 隔离打分 sub-agent（仅 Task tool 调用）
│   ├── cheatx-predict/                # 盲预测：完整 / 快押 / 批量
│   ├── cheatx-queue/                  # 定稿入队（队列 +1，改稿 ≥30% 触发 v2）
│   ├── cheatx-publish/                # 发布登记（队列 -1，正文一致性检查）
│   ├── cheatx-retro/                  # T+48h 数据回收 + 复盘（单条 / 批量）
│   ├── cheatx-persona/                # 受众画像（回复 + 引用聚类）
│   ├── cheatx-bump/                   # rubric 升级（含跨模型审）
│   ├── cheatx-recommend/              # 今日发帖推荐（1 稳 + 1 实验）
│   ├── cheatx-trends/                 # 热点抓取
│   ├── cheatx-status/                 # 状态看板
│   └── cheatx-migrate/                # schema 升级
├── shared-references/                 # 跨 skill 协议（三原则 / 预测结构 / 节奏 / 状态 / 候选 schema …）
├── starter-rubrics/
│   ├── x-post-zero.md                 # 单帖 / thread / 引用 / 回复 v0 起步 rubric
│   └── x-longform-zero.md             # 长帖 / Article v0 起步 rubric
├── templates/                         # 写进工作区的文件骨架（含 project-agents.template.md）
├── hooks/                             # immutability（阻塞）/ SessionStart 报告 / 使用日志
├── userscripts/
│   └── cheatx-exporter.user.js        # 油猴脚本：浏览 x.com 时导出帖子 / 回复 / 趋势 CSV
├── adapters/
│   ├── perf-data/x-csv-import/        # CSV 导入器（find / inspect / text / post / due / history / trends）
│   ├── perf-data/x-api/               # 可选：X API v2（按量计费）
│   └── trend-sources/                 # x-trends / aihot / trendradar-mcp
├── tools/                             # rank_check / calib_pool / leak_check / posted_text_check / diff_pct / score-curve
└── migrations/                        # schema 演进（x1.0 起）
```

---

## Tone & voice

跟用户说话：**像一个懂 X 的朋友，不像一个系统。**

- 短。一次只说一件事，给一个建议
- 不说内部术语：说"押注"不说"写 prediction 文件"，说"对答案"不说"跑 retro"，说"评分规则"不说"rubric_notes.md"——除非用户自己用了这些词
- 直接说失败：「打了 7.8 分但实际只有常态的 0.4 倍——规则高估了'会引发回复'这一项」
- **不要**用模糊措辞软化：「这或许可能在某种程度上暗示……」
- README 里的反叛 hook 只留在 README——**不要写进** `rubric_notes.md` 或预测日志

---

## 给开发者：扩展本 skill

- 新增数据导出来源（别的油猴脚本 / 插件）→ 在 `adapters/perf-data/x-csv-import/aliases.py` 加列名别名，或用 `--map`
- 新增热点源 → 加 `adapters/trend-sources/<name>.md`，符合 [candidate-schema.md](shared-references/candidate-schema.md)
- 修改原则 → 改 `shared-references/<protocol>.md`
- 修改托管模式的意图判断 → 改本文件"每句话先判断意图"那张表
- 修改斜杠命令路由 → 改本文件"斜杠命令速查"
- 与上游同步：`git fetch upstream` 后只挑方法论层（shared-references / 盲打 / bump）的改动合入，平台层（adapter / rubric）不合
