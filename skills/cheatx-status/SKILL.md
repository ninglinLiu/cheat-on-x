---
name: cheatx-status
description: cheat-on-x 的状态看板：到期待复盘、今天发了几条、队列颜色、校准进度与 confidence、偏差累计、是否该 bump、候选池、健康度。**任何时候都可调，只读，不改任何状态。**触发词："X 状态"/"状态"/"看板"/"status"/"我现在该做什么"。
allowed-tools: Bash(*), Read, Glob, Grep
---

# /cheatx-status — 状态看板

读 state + 扫项目 → 汇总 → 输出"现在该做什么"。

## Constants

- **STALE_SESSION_HOURS = 2**——`in_progress_session` 超过 2 小时视为中断
- **STALE_QUEUE_DAYS = 3**——队列里的帖子排了 3 天以上提醒时效
- **UNREGISTERED_PREDICTION_DAYS = 3**——预测写了 3 天以上既没定稿也没发布 → 问是不是弃稿 / 发了忘登记
- **RUBRIC_NOTES_LINE_WARN = 300**、**MEMO_OBS_WARN = 100**

## Inputs

`.cheatx-state.json`、`predictions/*.md`（header + 复盘段）、`candidates.md`、`rubric_notes.md` 行数、`rubric-memo.md` 观察条数、`.cheatx-cache/usage.jsonl`（如有）。

可以用确定性工具辅助：
```bash
python <cheat-on-x>/tools/calib_pool.py baseline predictions/ --json    # 各形态基线与样本数
python <cheat-on-x>/tools/calib_pool.py pool predictions/                 # 校准池（含 log score）
```

## Phase 1：派生指标

| 指标 | 算法 |
|---|---|
| 到期待复盘 | `pending_retros` 中 `due_at ≤ now` 的条数（列出最早几条） |
| 即将到期 | 24 小时内到期的条数 |
| 今日已发 | `recent_publishes` 中今天（本地时区）的主帖数 / `target_posts_per_day`；回复另计 |
| 距上一条主帖 | 分钟 |
| 队列 | `len(queue)`；颜色按 [cadence-protocol.md](../../shared-references/cadence-protocol.md)：`queue_days = len / posts_per_day`，`<0.5 🔴 / 0.5-1 🟠 / 1-3 🟢 / >3 🔵`；`posts_per_day = null` → 不显示颜色 |
| 队列最久 | `now − queue[0].queued_at` |
| 校准样本 / confidence | `calibration_samples` → 表见 state-management.md |
| 基线 | `baseline_impressions`（各形态） |
| 平均 log score（最近 20 条） | 从 calib_pool 输出；越接近 0 越好；和上一个 20 条比是变好还是变差 |
| 偏差累计 | `consecutive_directional_errors` |
| 未登记预测 | predictions/ 中没 `Published at`、也不在 queue 里、写于 3 天前以上的 |
| 候选池 | candidates.md 中非 skip / done、未过期的条数；距上次抓热点天数 |
| 健康度 | rubric_notes.md 行数、memo 观察条数、`leak_check` 结果、hooks、外部审核配置 |

## Phase 2：建议（按优先级，最多显示 6 条，其余折叠）

1. **到期待复盘 ≥ 1** → "先复盘：在 x.com 导出 CSV，然后说'复盘到期的'（文件自动找）"
2. **`in_progress_session` 中断**（> 2 小时）→ "上次的 <预测 / 批量预测 / bump> 没走完：继续还是清掉？"
3. **队列 🔴** → "今天的条数还没着落——说'推荐今天发什么'，我只推稳分 top 1"
4. **队列 🔵** 或最久一条排了 > 3 天 → "先发存货；排了 N 天的那条如果是热点可能已经过期"
5. **未登记预测** → "这几条预测写了 N 天：发了忘登记？（'已发 <链接>'）还是不发了？"
6. **偏差信号**（Claude 判断，同 cheatx-retro Phase 8）→ "建议 /cheatx-bump"，标 default-aligned / judgment-driven
7. **`leak_check` 失败** → "rubric_notes.md 里有疑似实际数据——盲打已不盲，先移到 rubric-memo.md"（高优先级）
8. **`last_prediction_self_scored = true`** → "上次预测没走盲打 sub-agent（N 天前）"
9. **confidence 跨档** → 🎉 通知（不需要确认任何东西）
10. **样本跨过 5 / 15 / 40** → 5：可以第一次 bump；15：可以 `/cheatx-bump --bucket-only`；40：bump 可以用数据驱动
11. **benchmark pending** → "跑 /cheatx-learn-from"
12. **benchmark imported 且你的数据已成为主信号**（默认 ≥15 条，Claude 可提前或推后）→ 通知
13. **初始化 > 24 小时、0 条预测、候选池空** → "跑 /cheatx-seed 拿第一批选题"
14. **hooks 没装** → "预测锁是君子协定"
15. **上次 bump 自审** → "配置 mcp__llm-chat__chat，下次 bump 走外部审核"
16. **rubric_notes.md 行数 / memo 观察条数超阈值** → "该清算了"
17. **数据路线是 x-api 且本月预估花费接近预算** → 提醒（按 usage.jsonl 里 x-api 调用记录粗估）

## Phase 3：输出

```
🎛️ cheat-on-x 状态（2026-11-14 21:15）
@yourhandle · Premium · 主要形态 single / thread · 目标每天 3 条
rubric v0 · 校准样本 12 · confidence 🟡 偏低（中枢 ±40%）
基线：single 420 · thread —（2 条，不足 3）· all 460
平均 log score（最近 12 条）：−1.48

⏰ 到期待复盘 3 条（最早 11-14 09:30）+ 24 小时内还有 2 条
📤 今天 1 / 3 · 距上一条 3 小时
📦 队列 1 条 ≈ 0.3 天 🔴

🎬 现在该做：
  1. 复盘 3 条：x.com 导出 CSV → "复盘到期的"（文件自动找）
  2. 队列 🔴：说"推荐今天发什么"
  3. 偏差：连续 3 次低估（2.4×, 3.1×, 2.2×）——再来一次就建议 bump；先看看是不是都发在 21 点后

🔥 候选池 14 条（tier1 5）· 距上次抓热点 4 天
📈 健康：rubric_notes 168 行 ✅ · leak_check ✅ · hooks ✅ · 外部审核 ❌
```

风格：直白、具体，每条建议附可以直接说的话或命令。

## Key Rules

1. 只读——任何状态修改是其他 skill 的事（`STATUS.md` 是本 skill 唯一写的文件，它只是看板快照）
2. 字段缺失写"未知"，不猜
3. 建议按优先级排，不一次堆 15 条
4. **不打印任何未到期帖子的数字**——看板只显示到期条数和时间，不显示它们的曝光

## Refusals

- 「顺便把复盘跑了」 → 拒绝，一次只做一件事；给出复盘命令
- 「看看我刚发那条现在多少浏览」 → 拒绝，窗口没到

## Integration

- 每个建议都路由到具体子 skill
- SessionStart hook（`hooks/session_start.py`）是本看板的精简版
