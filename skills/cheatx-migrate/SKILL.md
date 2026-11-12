---
name: cheatx-migrate
description: 把用户项目的 .cheatx-state.json 升级到当前 cheat-on-x 版本的 schema。读 migrations/registry.md 算迁移链 → dry-run → 备份 → 按顺序执行每步 → 验证。git pull 新版后、或 SessionStart 提示 schema 不一致后使用。触发词："迁移"/"升级 state"/"schema 版本不对"/"migrate"。
argument-hint: "[— to: <version>] [— from: <version>] [— dry-run]"
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# /cheatx-migrate — state schema 升级

哲学见 [migration-protocol.md](../../shared-references/migration-protocol.md)，版本链见 [migrations/registry.md](../../migrations/registry.md)。

> 当前 X 版只有 `x1.0` 一个 schema，还没有迁移步骤。本 skill 先把流程立好：将来 schema 升级时只需新增 `migrations/<from>-to-<to>.md`。

## Constants

- **REGISTRY = `<cheat-on-x>/migrations/registry.md`**
- **BACKUP = `.cheatx-state.json.backup-<unix 时间戳>`**（已在 .gitignore）

## Workflow

### Phase 0：迁移链

1. 读 `.cheatx-state.json` 的 `schema_version`、`edition`
   - `edition != "x"` 或 schema 不带 `x` 前缀（上游 `1.x`）→ 停下："这是上游 cheat-on-content 的 state，不能迁移成 X 版——两者单位、指标、窗口都不同。请在新目录 /cheatx-init"
2. 读 registry 的 `LATEST_SCHEMA`（`— to:` 可覆盖）
3. 相等 → "✅ 已是最新，无需迁移"，结束
4. state 比目标新 → 报错，不支持降级
5. 从"版本链"表串出 current → target 的每一步；某一步缺失 → 报错并列出已知版本

### Phase 1：dry-run

```
📋 迁移计划
当前 x1.0 → 目标 x1.1，共 1 步：
  [1/1] x1.0 → x1.1（MINOR）：新增字段 … · 详见 migrations/x1.0-to-x1.1.md
备份：.cheatx-state.json.backup-<ts>
继续？yes / no / detail
```

`— dry-run` 到此结束。

### Phase 2：备份

```bash
cp .cheatx-state.json .cheatx-state.json.backup-$(date +%s)
```

### Phase 3：逐步执行

对每一步：读 `migrations/<file>` 的 `## HOW (Claude steps)` 段，按自然语言步骤执行；完成后把 `schema_version` 设为该步的目标版本并**原子写**（.tmp → rename）。

失败 → 停在上一个成功的版本，不回滚：

```
❌ x1.0-to-x1.1 第 3 步失败：<原因>
state 停在 x1.0。修好后重跑 /cheatx-migrate 会从这里继续。备份在 <路径>。
```

### Phase 4：验证

能解析；`schema_version == target`；[state-management.md](../../shared-references/state-management.md) 的必填字段齐全。不通过 → 报告并指向备份。

### Phase 5：报告

```
✅ 迁移完成 x1.0 → x1.1（1 步）
备份：.cheatx-state.json.backup-<ts>（确认没问题后可以删）
CHANGELOG 提到 hook 脚本变化的话，再跑：bash <cheat-on-x>/install.sh --reinstall-hooks .
```

## Key Rules

1. 先 dry-run 再执行
2. 每次都备份
3. 不跳版，每步幂等
4. 失败停在原地
5. 只改 `.cheatx-state.json`（迁移文件明确要求时才动其他文件，并在 dry-run 里列出）

## Refusals

- 「直接改 schema_version 字段就行」 → 拒绝，字段内容不会跟着变
- 「把上游 cheat-on-content 的项目迁成 X 版」 → 拒绝，见 Phase 0
- 「降级」 → 拒绝，用 git 历史里的旧 state

## Integration

- SessionStart hook（`hooks/session_start.py`）检测到 schema 不一致时提示
- `install.sh --reinstall-hooks` 处理 hook 脚本更新；本 skill 只管 state
