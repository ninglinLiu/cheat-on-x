# Cadence Protocol（节奏协议）

被这些子 skill 引用：`cheatx-status`、`cheatx-recommend`、`cheatx-queue`、`cheatx-publish`、`cheatx-retro`、SessionStart hook。

固化"今天该做什么"——让 Claude 在会话开场就能回答"该复盘 / 该写 / 该发哪条"。

X 和视频平台节奏不同：一天可以发好几条；单条帖子的生命周期只有一两天；一小时内连发几条，后面的会被排序打折。所以 X 版的节奏单位是**"每天几条"**，队列按"够发几天"算，复盘按小时到期。

---

## 三层节奏

### 每次会话开场

SessionStart hook 渲染 4-6 行：
- ⏰ 到期待复盘（`pending_retros` 里 `due_at` ≤ 现在的条数）——**排第一**
- 📤 今天已发 N / 目标 M（只数主帖：single / thread / long / article / quote；reply 单独计）
- 📦 队列：N 条 ≈ 够发 X 天（颜色）
- 🎯 候选池 top 3
- ⚠️ 待办（schema 不一致 / 上次预测跳过了盲打 / 有中断流程）

不主动开始任何动作——等用户决定。

### 事件级（到期复盘）

`due_at` = `published_at` + `retro_window_hours`（长帖 / Article 用 `retro_window_hours_longform`）。到期 → SessionStart 顶部高亮。用户导出一次 CSV → `复盘到期的` 一次处理完。

### 每周

- `/cheatx-trends` 刷新候选池
- 看 `/cheatx-status` 的偏差累计和 bump 条件
- 清理 `rubric-memo.md` 的观察记录

---

## 队列（buffer）规则

**队列 = `state.queue`** = 已预测 + 已定稿、还没发的帖子。

`/cheatx-queue` 加入，`/cheatx-publish` 移出。

### 颜色（按 `target_posts_per_day` 派生）

`queue_days = len(queue) / target_posts_per_day`（只数主帖；reply 不进队列）

| queue_days | 颜色 | 含义 | 行动 |
|---|---|---|---|
| < 0.5 | 🔴 红 | 今天的条数都没着落 | 先写稳分的（推荐 top 1），别等灵感 |
| 0.5 – 1 | 🟠 橙 | 只够今天 | 写 1-2 条补上 |
| 1 – 3 | 🟢 绿 | 正常 | 可写可休 |
| > 3 | 🔵 蓝 | 积压 | 停写，先发；X 帖子时效衰减快，排三天以上的热点稿可能已经过期 |

`target_posts_per_day = null` → 不显示颜色，只显示"队列 N 条"。

---

## 发帖间隔

X 排序对同一作者在同一个人时间线里的连续出现做衰减。具体系数没有公开，所以这里只给保守默认：

- **主帖之间建议 ≥ 2 小时**（`MIN_SPACING_MINUTES = 120`，可在 state 里改）
- `cheatx-publish` 登记时算"距上一条主帖 N 分钟"写进 header；< 间隔 → 提示一次，不阻止
- `cheatx-recommend` 给发布时间建议时避开间隔不足的时段
- 这个间隔本身是假设——协变量里记着"距上一条帖子"，bump 时可以检验它

---

## 推荐策略（`/cheatx-recommend`）

每次推荐：**1 稳 + 1 实验**。

### 稳

- 候选池 composite top 1-3
- 话题类别与最近 N 条主帖**不重复**（N = max(3, target_posts_per_day × 2)）
- NR ≤ 1

### 实验

- 能验证某个**待验证假设**的候选（`rubric-memo.md` 里的候选维度 / 某形态的倍数 / 某时段）
- 或验证 `post_patterns.md` 里某个单样本待验证的 pattern
- composite 不一定高，但复盘后信息量大

### 队列颜色覆盖

| 颜色 | 覆盖 |
|---|---|
| 🔴 | 只推稳的 top 1 |
| 🟠 | 1 稳 + 1 实验，先写稳的 |
| 🟢 | 标准 1 + 1 |
| 🔵 | 暂停推荐："队列已经够发 N 天，先发" |

**任何颜色都遵守**：同一类别连发 ≤ 2 条；标 `done` 的候选不推；用户跳过（`skip`）的 30 天内不推。

---

## 元规则（优先级从高到低）

1. **复盘优先于新写**：有到期复盘时先复盘——一次 CSV 导出就能清掉一批，拖久了回复区会沉底，评论信号丢失
2. **盲预测优先于发**：没写预测的帖子不要发；实在要发，就接受它不进校准池（`_redo` reconstructed）
3. **节奏优先于完美**：🔴 时发一条 composite 6.5 的稳分帖，好过等明天的 8.5
4. **实验最多一半**：每天至少一半主帖是稳分的。冷启动期实验失败率高

---

## 标准"今日工作流"

### 有到期复盘

```
SessionStart：⏰ 3 条到期
→ 用户在 x.com 打开自己主页，油猴脚本导出 CSV（或 x-api）
→ "复盘到期的 imports/x-posts-xxxx.csv" → cheatx-retro 批量
→ 每条写复盘段 → 检查 bump 条件
```

### 队列偏低

```
SessionStart：📦 🔴 队列 0 条
→ "推荐今天发什么" → cheatx-recommend 只推稳分 top 1
→ cheatx-seed 写草稿 / 用户自己写 → "快押 drafts/..." → "定稿 ..." → 发 → "已发 <url>"
```

### 日常批量

```
一次写 3-5 条草稿 → "批量预测 drafts/" → 盲打 sub-agent 一次打完 → 用户逐条 ok
→ 每条 "定稿" 入队 → 按推荐时段发 → 每发一条 "已发 <url>"
```

---

## 偏离时

只显式报告，不自动补救：

```
❌ 已 N 天没有发主帖（最后一次：YYYY-MM-DD），队列 0 条
```

```
❌ 队列 N 条已够发 X 天，其中 K 条入队超过 3 天——时效性在流失
```

```
❌ 有 N 条帖子已发布但没登记（publish 后才知道），这些不会进校准池
```

---

## 子 skill 责任表

| Skill | 节奏责任 |
|---|---|
| `/cheatx-init` | 问每天几条、复盘窗口；装 SessionStart hook |
| `/cheatx-queue` | 加入 `state.queue` |
| `/cheatx-publish` | 移出 `state.queue`；写 `recent_publishes`、`pending_retros`（含 `due_at`）；算发帖间隔 |
| `/cheatx-status` | 算颜色、今日条数、到期复盘 |
| `/cheatx-recommend` | 按颜色 + 1 稳 1 实验 + 间隔给推荐 |
| `/cheatx-retro` | 移出 `pending_retros`；复盘后重算该形态基线 |
| SessionStart hook | `hooks/session_start.py` 渲染报告 |
