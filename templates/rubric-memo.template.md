# Rubric Memo — 观察与升级档案（rubric-memo.md）

> ⚠️ **Channel B（`cheatx-score-blind` sub-agent）永远不读本文件**——它在 sub-agent 的硬禁读清单里（refusal_code `blocked_rubric_memo`）。
>
> 这里放所有**带真实数据**的东西：每次复盘的观察记录、跨样本观察、待验证假设、每次 bump 的完整 Memo、被拒的升级、基线重算记录。

| 文件 | 内容 | blind 可读 |
|---|---|---|
| `rubric_notes.md` | 公式 / 维度定义 / bucket 规则 / 抽象规律 | ✅ |
| `rubric-memo.md`（本文件） | 观察 + Memo，含帖子名、链接、数字、回复摘录 | ❌ |

生命周期规则见 cheat-on-x 的 `shared-references/observation-lifecycle.md`。

---

## 观察记录

> `/cheatx-retro` 每次复盘追加一条（批量复盘可合并成一张表）。被吸收 / 被推翻的条目在 bump cleanup 时删除——git history 是档案。
>
> ```
> ### YYYY-MM-DD [短名] (id) — [一句话定性]
> - 形态 / 协变量：
> - 预测：composite=X.XX，bucket=…，中枢 N
> - 实际：曝光 N（实际/中枢 N.N×）· 互动率 · 收藏/赞比 · 回复（T+48h）
> - 回复 / 引用要点：
> - 判断：
> - 详见：predictions/<file>.md
> ```

（暂无）

---

## 重大跨样本观察

> 同一 pattern ≥3 条样本支持才升格到这里。

（暂无）

---

## 待验证假设

- [ ] [示例] 晚间 21-23 点发的主帖曝光高于白天（协变量：发帖时段）
- [ ] [示例] thread 相对 single 的倍数（形态基线差异）
- [ ] [示例] TM（时效）维度是否有独立预测力

---

## 基线 / bucket 重算记录

> `/cheatx-retro` 每次重算某形态基线、或 `/cheatx-bump --bucket-only` 时追加一行。

| 日期 | 形态 | 旧基线 | 新基线 | 样本数 |
|---|---|---|---|---|

---

## 升级 Memo

> `/cheatx-bump` Step 5 在这里 append，旧 Memo 不动。每段 6 个组件：

```markdown
---

## v<N> → v<N+1> Memo（bumped at <ISO 8601>）

### 触发观察
（观察 ID + 一句话）

### 证据数据
`tools/rank_check.py` 完整输出 + 校准池重算表：

| 样本 | 形态 | composite (vN) | composite (vN+1) | 实际/基线 | 备注 |
|---|---|---|---|---|---|

### 诊断
（vN 的哪条假设被推翻；vN+1 为什么能解释）

### 新公式
旧：`…`
新：`…`
变化：…

### 跨模型审核（channel C）
- 审核模型：
- 判定：PASS / REJECT
- 理由摘录：

### 已知局限
```

（首次 bump 后在此追加第一段）

---

## 被拒升级 log

> 提议过但没通过的 bump——避免半年后重复提同一个失败方案。

（暂无）
