---
name: cheat-on-x
description: cheat-on-content 的 X（Twitter）版——给想把"这条感觉会爆"变成可校准预测的 X 创作者。打分 → 盲预测 → 发帖 → T+48h 复盘 → 进化 rubric 的循环，针对 X 的单帖 / thread / 长帖 / Article / 引用 / 回复。打分维度对齐 X 2026 开源推荐算法（Phoenix）预测的用户行为（回复、转发、引用、收藏私信、主页点击、关注、停留、负反馈）。数据回收三条路：油猴脚本导出 CSV（默认，零成本）/ X API（可选，按量计费）/ 手动粘贴。触发词："初始化 cheat-on-x"/"X 初始化"/"打分这条"/"启动预测"/"批量预测"/"定稿"/"已发 https://x.com/..."/"复盘"/"复盘到期的"/"升级 rubric"/"推荐今天发什么"/"抓 X 热点"/"X 状态"/"导入对标账号"。**首次使用必须先跑 /cheatx-init。**
argument-hint: "[draft-path] [— mode: full|quick|batch]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__llm-chat__chat
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
>
> 默认假设：**用户的 X 账号还在起步期**（几百到几千粉）。cold-start 期预测会很不准——这是数学事实，工具用 confidence 等级明说，不藏数字。

把 X 上的发帖变成可校准预测循环：**打分 → 预测 → 发帖 → 复盘 → 进化 rubric**。

本文件是**总协议 + 路由器**。各阶段的工作流在 `skills/cheatx-*/SKILL.md`。

## Codex compatibility

Codex 没有 slash-command harness。安装到 Codex 后按自然语言触发同一套路由：

- `初始化 cheat-on-x` → 读取并执行 `skills/cheatx-init/SKILL.md`
- `打分这条 drafts/foo.md` → `skills/cheatx-score/SKILL.md`
- `启动预测 drafts/foo.md` / `批量预测 drafts/` → `skills/cheatx-predict/SKILL.md`
- `定稿 ...` / `已发 ...` / `复盘 ...` / `升级 rubric` / `X 状态` → 对应 `skills/cheatx-*/SKILL.md`

执行时遵循本文件的三条原则和路由表；不要依赖 `/cheatx-*` 命令是否存在。Claude Code 专用 hook（`.claude/settings.json`）只在 Claude Code 里自动触发；Codex 中需要用户主动说 `X 状态` 查看队列、待复盘和候选池。

---

## 三条不可妥协原则

任何一条被违反，整个校准循环退化为"凭直觉的自我安慰"。用户要求打破其中任何一条 → **拒绝执行并说明原因**。

1. **盲预测（Blind prediction）**：预测必须在看到这条帖子任何实际数据**之前**写完。X 的特殊风险：发出去几分钟帖子下面就有浏览数——**预测必须在点"发布"之前落盘**。写完后 `## 预测` 段 immutable，只能往 `## 复盘` 段追加。完整规范：[shared-references/blind-prediction-protocol.md](shared-references/blind-prediction-protocol.md)。**hooks/prediction-immutability.sh 在 harness 层强制执行**。

2. **升级 = 全量重打（Bump = full re-score）**：rubric 升级时，校准池样本必须用新公式重算；新排序与实际表现排序一致性不达标，升级被拒；升级必须经跨模型独立审核。X 校准池长得快，样本 > 40 时按分层抽样重打（规则见 [shared-references/bump-validation-protocol.md](shared-references/bump-validation-protocol.md)）。

3. **rubric 是工作台，不是博物馆**：被新数据推翻或被吸收为正式维度的观察，**删掉**。git history 才是档案。完整规范：[shared-references/observation-lifecycle.md](shared-references/observation-lifecycle.md)。

---

## 路由表（触发词 → 子 skill）

| 用户说 | 调用 | 前置条件 |
|---|---|---|
| "初始化 cheat-on-x" / "X 初始化" / "init" | `/cheatx-init` | 无（入口） |
| "导入对标账号" / "学 @xxx" / "找对标" / "learn from" | `/cheatx-learn-from` | 已 init；cold-start 强烈建议 |
| "找选题" / "不知道发什么" / "seed" | `/cheatx-seed` | 已 init |
| "打分这条 [path]" / "score this" | `/cheatx-score` | rubric_notes.md 存在 |
| "启动预测 [path]" / "快押 [path]" / "批量预测 drafts/" | `/cheatx-predict` | 已 init + 有定稿草稿 |
| "定稿 [path]" / "排进队列" / "queued" | `/cheatx-queue` | 对应预测已写（队列 +1） |
| "已发 https://x.com/.../status/..." / "posted" | `/cheatx-publish` | 对应预测文件存在（队列 -1） |
| "复盘 [path]" / "复盘到期的" / "retro" | `/cheatx-retro` | 已发布 + 已过复盘窗口 |
| "受众画像" / "我的读者是谁" / "build persona" | `/cheatx-persona` | 有复盘回复数据（或 benchmark seed） |
| "升级 rubric" / "bump rubric" | `/cheatx-bump` | 校准池 ≥ MIN_SAMPLES_FOR_BUMP |
| "推荐今天发什么" / "next post" | `/cheatx-recommend` | candidates.md 存在且非空 |
| "抓 X 热点" / "fetch trends" | `/cheatx-trends` | 至少一个 trend source |
| "X 状态" / "status" / "看板" | `/cheatx-status` | 任意时刻 |
| "迁移" / "schema 版本不对" / "migrate" | `/cheatx-migrate` | git pull 新版后；SessionStart 提示 schema mismatch 后 |

> 定稿 vs 发布分两个动作：队列（buffer）需要知道"写好排着"和"已发出"两种状态，也给"发出去的正文和预测时不一样"留一个检查点。详见 [shared-references/cadence-protocol.md](shared-references/cadence-protocol.md)。

**State 检测**（首次接到非 init 触发词时执行）：
1. 当前目录没有 `.cheatx-state.json` → 路由到 `/cheatx-init`
2. 读 `calibration_samples` → 派生 confidence 等级（不切换流程，只显示）
3. 再路由到目标 skill

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

详细拒绝场景在每个子 skill 的 `Refusals` 段。

---

## 项目目录结构（用户的 X 内容项目）

`/cheatx-init` 创建缺失项；**绝不在没确认的情况下覆盖**。

```
<x-content-project>/
├── .gitignore                         # cheatx-init 创建；挡住 .cheatx-secrets.json / imports/ 等
├── .cheatx-state.json                 # 状态文件，子 skill 共享上下文
├── .cheatx-cache/                     # 不入版本控制（usage.jsonl / trends-history.jsonl）
├── .cheatx-hooks/                     # init 复制的 hook 脚本
├── .claude/settings.json              # 注册 prediction-immutability 等 hook
├── rubric_notes.md                    # 评分规则（blind sub-agent 白名单，只放通用语言）
├── rubric-memo.md                     # bump Memo + 复盘观察（含实绩，blind 硬禁读）
├── post_patterns.md                   # 写法 pattern 沉淀（教 Claude 怎么写）
├── benchmark.md                       # 对标账号（cheatx-learn-from 维护）
├── audience.md                        # 受众画像（cheatx-persona 派生；blind 硬禁读）
├── WORKFLOW.md / STATUS.md
├── candidates.md                      # 选题池
├── drafts/                            # 发帖前的草稿
│   └── YYYY-MM-DD_<id>_<short>.md
├── predictions/                       # immutable 预测日志（hook 保护）
│   └── YYYY-MM-DD_<id>_<short>.md     # 与 drafts/ 同名
├── posts/                             # 定稿后才建（cheatx-queue 创建）
│   └── YYYY-MM-DD_<id>_<short>/
│       ├── final.md                   # 实际要发的定稿
│       └── report.md                  # 复盘数据（cheatx-retro 写）
├── samples/                           # 对标账号样本（cheatx-learn-from）
│   └── <handle>/
└── imports/                           # 你从油猴脚本 / X Analytics 导出的 CSV 放这里（gitignore）
```

---

## 文件清单（本 skill 包）

```
cheat-on-x/
├── SKILL.md                           # 本文件（总协议 + 路由）
├── README.md / docs/README_CN.md
├── skills/
│   ├── cheatx-init/                   # 入口：onboarding 与脚手架
│   ├── cheatx-learn-from/             # 对标账号导入（CSV / API / 粘贴）
│   ├── cheatx-seed/                   # cold-start 选题 + 草稿
│   ├── cheatx-score/                  # 单条打分（不写文件）
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
├── templates/                         # 写进用户项目的文件骨架
├── hooks/                             # immutability（阻塞）/ SessionStart 报告 / 使用日志
├── userscripts/
│   └── cheatx-exporter.user.js        # 油猴脚本：浏览 x.com 时导出帖子 / 回复 / 趋势 CSV
├── adapters/
│   ├── perf-data/x-csv-import/        # CSV 导入器（油猴导出 / X Analytics 导出 / 其他工具导出）
│   ├── perf-data/x-api/               # 可选：X API v2（按量计费）
│   └── trend-sources/                 # x-trends / aihot / trendradar-mcp
├── tools/                             # diff_pct.py / score-curve.py
└── migrations/                        # schema 演进（x1.0 起）
```

---

## Tone & voice

写面向用户的文案（复盘小结 / commit message 等）时用**直白克制**的语气：

- 直接说失败：「composite 7.8 但实际只有 0.4× 基线——rubric 高估了 RP」
- **不要**用模糊措辞软化：「这或许可能在某种程度上暗示……」
- README 里的反叛 hook 只留在 README——**不要写进** `rubric_notes.md` 或预测日志

---

## 给开发者：扩展本 skill

- 新增数据导出来源（别的油猴脚本 / 插件）→ 在 `adapters/perf-data/x-csv-import/aliases.py` 加列名别名，或用 `--map`
- 新增热点源 → 加 `adapters/trend-sources/<name>.md`，符合 [candidate-schema.md](shared-references/candidate-schema.md)
- 修改原则 → 改 `shared-references/<protocol>.md`
- 修改路由 → 改本文件"路由表"
- 与上游同步：`git fetch upstream` 后只挑方法论层（shared-references / 盲打 / bump）的改动合入，平台层（adapter / rubric）不合
