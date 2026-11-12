# Migrations Registry

cheat-on-x 的 schema 版本演进单一来源。`/cheatx-migrate` 读这份文件决定要跑哪些迁移。

X 版的 schema 链**独立于上游** cheat-on-content（上游是 1.0 → 1.4）。X 版从 `x1.0` 起步，版本号带 `x` 前缀，避免和上游 state 文件混淆。

---

## 当前 schema_version

**`x1.0`** —— 由 `cheatx-init` Phase 3 写入新 state 文件。

`LATEST_SCHEMA` 标记位被 `cheatx-migrate` skill 和 SessionStart hook（`hooks/session_start.py`）引用：

```
LATEST_SCHEMA = "x1.0"
```

> 维护者注意：bump 这个值的同时**必须**新增迁移文件 + 在下方"版本链"追加一行 + 同步改 `hooks/session_start.py` 里的 `LATEST_SCHEMA`。

---

## 版本链

| from | to | breaking? | 迁移文件 | 描述 |
|---|---|---|---|---|
| (none) | x1.0 | — | (内置) | X 版首版 schema。相对上游 1.4：`shoots` → `queue`；`baseline_plays` → 按形态的 `baseline_impressions`；`target_publish_cadence_days` → `target_posts_per_day`；`typical_duration_seconds` 删除；新增 `x_handle` / `x_premium` / `forms_enabled` / `retro_window_hours*` / `x_api` / `recent_publishes` / `edition`；`pending_retros` 项从路径字符串变成带 `due_at` 的对象。上游 1.4 引入的 rubric_notes / rubric-memo 拆分**从第一天就是默认** |

### 从上游 cheat-on-content 迁过来？

不支持自动迁移——两边的单位（视频 vs 帖子）、指标（播放 vs 曝光）、窗口（T+3d vs T+48h）都不同，旧样本不能直接当 X 校准样本。做法：在新目录 `/cheatx-init`，把旧项目的 `rubric-memo.md` 当参考读一遍即可。

---

## 迁移文件命名约定

- 文件名：`<from>-to-<to>.md`（如 `x1.0-to-x1.1.md`）
- 每份必含 4 段：
  1. **WHAT changed** — 字段层 diff（新增 / 删除 / 重命名）
  2. **WHY** — 为什么改
  3. **HOW (Claude steps)** — Claude 跑 `/cheatx-migrate` 时按顺序执行的步骤
  4. **Manual fallback** — 用户不想跑 skill 时手改 `.cheatx-state.json` 的最小指令

---

## 哲学（详见 [shared-references/migration-protocol.md](../shared-references/migration-protocol.md)）

- **MINOR**（x1.0 → x1.1）：只新增字段或放宽 enum。老 state 用 `state.get(field, default)` 读默认值，可以不跑 migrate
- **MAJOR**（x1.x → x2.0）：删字段 / 重命名 / 改语义。必须跑 migrate
- **不允许跳版**：按顺序逐步跑，每步幂等
- **失败停在原地**：第 N 步失败 → schema_version 仍是 N-1，修好后重跑从断点继续

---

## 给开发者：新增一个迁移

1. 判断 MINOR 还是 MAJOR
2. 改 `skills/cheatx-init/SKILL.md` 里写入的 `schema_version`
3. 改本文件 `LATEST_SCHEMA`，同步 `hooks/session_start.py`
4. "版本链"表追加一行
5. 新建 `migrations/<old>-to-<new>.md`，4 段都填
6. CHANGELOG.md 标 `BREAKING` 或 `MINOR`
7. 在 fixture 老 state 上跑 `/cheatx-migrate` 验证
