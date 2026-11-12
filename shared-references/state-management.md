# State Management（状态文件读写约定）

被所有子 skill 引用。`.cheatx-state.json` 是各子 skill 共享上下文的**单一来源**——运行时状态、累计指标、配置都从这里读、写回这里。

---

## 文件位置

```
<x-content-project>/.cheatx-state.json
```

**绝不**放到全局 `~/.claude/` 或 cheat-on-x 源码目录——一个用户可能有多个 X 账号 / 项目，每个项目独立状态。

文件名带 `x`（不是上游的 `.cheat-state.json`），这样同一台机器可以同时装 cheat-on-content 和 cheat-on-x，互不串台。

---

## 完整 schema（x1.0）

```json
{
  "schema_version": "x1.0",
  "skill_version": "0.1.0",
  "edition": "x",

  "x_handle": "@yourhandle",
  "x_premium": "none",
  "followers_at_init": 820,
  "primary_language": "zh",
  "content_form": "x-post",
  "forms_enabled": ["single", "thread", "quote", "reply"],
  "target_posts_per_day": 3,
  "retro_window_hours": 48,
  "retro_window_hours_longform": 168,

  "rubric_version": "v0",
  "benchmark_status": "none",
  "benchmark_handles": [],
  "benchmark_sample_count": 0,
  "baseline_impressions": {
    "all": null, "single": null, "thread": null, "long": null,
    "article": null, "quote": null, "reply": null
  },
  "baseline_updated_at": null,

  "calibration_samples": 0,
  "calibration_samples_at_last_bump": 0,

  "data_collection": "csv",
  "enabled_perf_adapters": ["x-csv-import"],
  "x_api": { "enabled": false, "user_context": false, "budget_usd_per_month": null },
  "pool_status": "none",
  "data_layer": "markdown",

  "hooks_installed": false,
  "enabled_trend_sources": ["manual-paste"],

  "last_bump_at": null,
  "last_bump_self_audited": false,
  "last_published_at": null,
  "last_published_file": null,
  "last_retro_at": null,
  "last_trends_run_at": null,
  "last_trends_added_count": 0,
  "last_prediction_self_scored": false,
  "last_self_scored_at": null,

  "consecutive_directional_errors": [],
  "pending_retros": [],
  "queue": [],
  "recent_publishes": [],

  "in_progress_session": null,

  "initialized_at": "2026-11-12T15:00:00+08:00"
}
```

---

## 字段说明

### 元数据

| 字段 | 类型 | 写入者 | 说明 |
|---|---|---|---|
| `schema_version` | string | cheatx-init / cheatx-migrate | 当前 `"x1.0"`。X 版的 schema 链独立于上游（上游 1.x），见 [migrations/registry.md](../migrations/registry.md) |
| `skill_version` | string | cheatx-init | cheat-on-x 版本 |
| `edition` | `"x"` | cheatx-init | 固定值。防止误把上游 state 文件当成 X 版读 |
| `initialized_at` | ISO 8601（本地时区，**不要 `Z`**） | cheatx-init | 永不变 |

### 账号与形态

| 字段 | 取值 | 写入者 | 读取者 | 说明 |
|---|---|---|---|---|
| `x_handle` | `"@xxx"` | cheatx-init | cheatx-publish / retro / csv 导入（区分"我的帖子"和别人的） | 不带 `@` 也接受，读时统一补 |
| `x_premium` | `none` / `basic` / `premium` / `premium_plus` / `unknown` | cheatx-init（用户变更时手改） | cheatx-predict（记为协变量） | Premium 影响回复区排序和长帖能力。**不进 composite**，只作为发布条件记录 |
| `followers_at_init` | int / null | cheatx-init | cheatx-predict（cold-start 基线猜测） | 每条预测的发帖时粉丝数另记在预测 header |
| `primary_language` | `zh` / `en` / `mixed` | cheatx-init | cheatx-seed / cheatx-score-blind | 决定草稿语言 |
| `content_form` | `x-post` / `x-longform` / `x-mixed` | cheatx-init | cheatx-predict / cheatx-recommend | 决定起步 rubric：`x-post` → x-post-zero；`x-longform` → x-longform-zero；`x-mixed` → x-post-zero（长帖按其中长文条款打） |
| `forms_enabled` | 数组：`single` / `thread` / `long` / `article` / `quote` / `reply` | cheatx-init | cheatx-seed / cheatx-predict / cheatx-recommend | 用户实际会发的形态 |
| `target_posts_per_day` | int / null | cheatx-init | cheatx-status / recommend / queue / publish / SessionStart | 每天目标条数；null = 灵活（关闭队列警戒） |
| `retro_window_hours` | int | cheatx-init | cheatx-retro / cheatx-publish / SessionStart | 默认 48 |
| `retro_window_hours_longform` | int | cheatx-init | 同上 | `long` / `article` 形态用，默认 168（7 天） |

### 校准

| 字段 | 写入者 | 说明 |
|---|---|---|
| `rubric_version` | cheatx-init / cheatx-bump | `v0` → `v1` … |
| `benchmark_status` | cheatx-init / cheatx-learn-from | `none` / `pending` / `imported` |
| `benchmark_handles` | cheatx-learn-from | 已导入的对标账号 handle 列表 |
| `benchmark_sample_count` | cheatx-learn-from | 已导入的对标帖子数 |
| `baseline_impressions` | cheatx-init / cheatx-retro / cheatx-bump `--bucket-only` | 按形态的曝光基线 = 该形态**最近 10 条已复盘帖**的曝光中位数（不足 3 条时为 null，回落 `all`）。`all` = 所有形态最近 10 条中位数 |
| `baseline_updated_at` | 同上 | 最近一次重算时间 |
| `calibration_samples` | cheatx-retro（每次复盘 +1） | 进度 / confidence / bump 门槛 |
| `calibration_samples_at_last_bump` | cheatx-bump | "距上次 bump 多少新样本" |

### 数据与工具配置

| 字段 | 取值 | 写入者 | 说明 |
|---|---|---|---|
| `data_collection` | `csv` / `x-api` / `manual` | cheatx-init | 复盘默认数据路径。`csv` = 油猴脚本或 X Analytics 导出 → [x-csv-import](../adapters/perf-data/x-csv-import/README.md) |
| `enabled_perf_adapters` | `["x-csv-import"]` / `["x-api", "x-csv-import"]` / `[]` | cheatx-init / 用户手改 | 空 → 手动粘贴 |
| `x_api.enabled` | bool | cheatx-init | 是否配置了 Bearer Token（token 本身放 `.cheatx-secrets.json` 或环境变量，**不进 state**） |
| `x_api.user_context` | bool | cheatx-init | 是否有用户授权 token（可拿主页点击 / 链接点击，仅本人 30 天内帖子） |
| `x_api.budget_usd_per_month` | number / null | cheatx-init | 用户给的月预算；x-api 调用前估算费用，超预算先问 |
| `pool_status` | `none` / `markdown` / `notion` | cheatx-init / cheatx-recommend | 选题池 |
| `data_layer` | `markdown` / `sqlite` | cheatx-init | 当前只用 markdown |
| `hooks_installed` | bool | cheatx-init | |
| `enabled_trend_sources` | 数组 | cheatx-init / 用户手改 | 如 `["x-trends", "aihot", "manual-paste"]` |

### 时间戳

`last_bump_at` / `last_published_at` / `last_retro_at` / `last_trends_run_at` / `last_self_scored_at`：ISO 8601 或 null。
`last_published_file`：最近一次发布的预测文件路径。
`last_bump_self_audited`：bump 是否走了自审（`CROSS_MODEL_AUDIT=false`）。
`last_trends_added_count`：上次抓热点新增候选数。
`last_prediction_self_scored`：上次预测是否跳过 blind sub-agent。

### 列表队列

| 字段 | 写入者 | 读取者 | 项结构 |
|---|---|---|---|
| `consecutive_directional_errors` | cheatx-retro（push）/ cheatx-bump（清空） | cheatx-status / retro | `{"dir": "high"\|"low", "ratio": 0.31, "file": "..."}`；`ratio` = 实际 / 中枢 |
| `pending_retros` | cheatx-publish（push）/ cheatx-retro（remove） | cheatx-status / SessionStart / retro `due` | `{"file", "status_id", "form", "published_at", "due_at"}`；`due_at` = published_at + 对应窗口 |
| `queue` | cheatx-queue（push）/ cheatx-publish（remove） | cheatx-status / recommend / SessionStart | `{"post_folder", "prediction_file", "drafts_path", "queued_at", "planned_at", "final_consistency", "final_diff_pct", "v2_prediction_written", "final_hash_at_queue"}`。`len(queue)` = 队列条数 |
| `recent_publishes` | cheatx-publish（push，保留最近 30 条） | cheatx-status / recommend / SessionStart | `{"at", "status_id", "form"}`。用于"今天已发 N / 目标 M"和发帖间隔提醒 |

### 会话状态

`in_progress_session`：多步流程中途的标记，流程结束清回 null。

```json
{ "type": "prediction" | "batch_prediction" | "bump",
  "files": ["predictions/2026-11-12_a3f2c1d4e5b6_ai写作.md"],
  "started_at": "2026-11-12T14:00:00+08:00",
  "rubric_version": "v0" }
```

cheatx-status 发现它非 null 且超过 2 小时 → 提示"有一个中断的流程，要继续还是清掉？"。

---

## 读写协议

### 读（任何 skill）

```python
import json, os
state_path = os.path.join(os.getcwd(), ".cheatx-state.json")
if not os.path.exists(state_path):
    raise NeedsInitError()          # → 路由 /cheatx-init
state = json.load(open(state_path, encoding="utf-8"))
if state.get("edition") != "x":
    warn("这不是 cheat-on-x 的 state 文件")   # 可能是上游 .cheat-state.json 被改名
LATEST_SCHEMA = "x1.0"   # 见 migrations/registry.md
if state.get("schema_version") != LATEST_SCHEMA:
    warn("schema 不一致，建议 /cheatx-migrate")   # 非阻塞
```

- 一律 `state.get(field, default)` 容错——新版加字段时旧文件缺字段要优雅默认
- 内存里改了 state 必须写回磁盘，下游 skill 读的是磁盘版

### 写（任何 skill）

```python
def write_state(state):
    path = os.path.join(os.getcwd(), ".cheatx-state.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)   # 原子替换
```

原子写、`indent=2`、`ensure_ascii=False`、写完再继续后续操作。

### 并发模型

单用户 + 单会话，不加锁。两个会话同时操作同一项目可能写覆盖——不推荐。

---

## 字段写入责任表

| 字段 | 唯一写入者 |
|---|---|
| `rubric_version` | cheatx-init / cheatx-bump |
| `baseline_impressions` | cheatx-init（导入历史时）/ cheatx-retro（每次复盘后重算该形态）/ cheatx-bump `--bucket-only` |
| `calibration_samples` | cheatx-retro |
| `pending_retros` | cheatx-publish（push）/ cheatx-retro（remove） |
| `queue` | cheatx-queue（push）/ cheatx-publish（remove） |
| `recent_publishes` | cheatx-publish |
| `consecutive_directional_errors` | cheatx-retro（push）/ cheatx-bump（清空） |
| `in_progress_session` | 发起该流程的 skill（创建 + 清除） |
| `last_bump_at` | cheatx-bump |

**不允许**多个 skill 写同一字段。新增字段先想好唯一写者。

---

## 损坏 / 不一致的处理

| 症状 | 处理 |
|---|---|
| 文件不存在 | 提示跑 /cheatx-init，**不**自动创建 |
| JSON 解析失败 | 报路径，建议手修或备份后重 init |
| `edition` ≠ `"x"` | 提示"这是上游 cheat-on-content 的 state"，不继续 |
| schema_version 不识别 | 建议 /cheatx-migrate |
| `pending_retros` 指向已删除文件 | cheatx-status 安静移除 |
| `queue` 项的 post_folder 不存在 | cheatx-status 报告，询问是否移除 |
| `calibration_samples` 与 predictions/ 中已复盘文件数不一致 | cheatx-status 报差异 |

---

## 与 git 的关系

`.cheatx-state.json` **入库**（项目配置 + 累计指标快照，多设备同步靠 git）。**不含**任何凭证。

**不入库**（cheatx-init 写进 `.gitignore`）：
- `.cheatx-secrets.json`（X API token）
- `.cheatx-cache/`（本地日志 / 去重缓存）
- `.cheatx-hooks/`（init 复制的 hook 脚本副本）
- `imports/`（油猴 / Analytics 导出的原始 CSV：含别人的回复和 handle，原始导出只留本地；复盘结论在 report.md 里入库）

---

## 用户手改边界

可以手改：`enabled_trend_sources`、`data_collection`、`enabled_perf_adapters`、`x_premium`、`target_posts_per_day`、`retro_window_hours*`、`x_api.budget_usd_per_month`。

不建议手改：`calibration_samples`、`pending_retros`、`queue`、`consecutive_directional_errors`、`rubric_version`、`baseline_impressions`——它们应由流程更新。想重置 → 删整个 `.cheatx-state.json` 重跑 /cheatx-init。

---

## Confidence label 派生表（**单一真值**）

被 cheatx-predict / status / recommend / SessionStart 共用，从 `calibration_samples` 派生：

| `calibration_samples` | 标签 | 含义 | 怎么用 |
|---|---|---|---|
| 0 | 🔴 极低 | 占星级别，纯纪律训练 | 不要据此决定发不发；预测是为了**采集数据** |
| 1-4 | 🟠 低 | 中枢 ±60%，只信方向 | 信"A 比 B 好"，不信具体数字 |
| 5-14 | 🟡 偏低 | 中枢 ±40% | bucket 排序可用 |
| 15-39 | 🟢 中 | 中枢 ±25% | 可作为发不发、先发哪条的依据之一 |
| 40-99 | 🟢 较高 | 中枢 ±15% | 可信中枢估计 |
| 100+ | 🔵 高 | 中枢 ±10% | 进入数据驱动阶段——bump 可用回归 |

> 档位比上游宽：X 一天能产出好几个样本，但单条帖子的方差也比视频大（一条被大号转一下就是 30×）。±X% 是经验猜测，不是保证；你的真实收敛速度看 `tools/score-curve.py`。

**不要用这个表 gating 任何功能**——所有 calibration_samples 下都跑相同流程，只是输出里显示 confidence。
