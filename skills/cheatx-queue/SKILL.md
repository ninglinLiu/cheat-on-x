---
name: cheatx-queue
description: 登记一条帖子"定稿、排队待发"。建 posts/<id>/ 目录 + 写 final.md（实际要发的文本）+ 定稿与草稿差 ≥30% 时触发 v2 预测 + 队列 +1。与 cheatx-publish 配对：定稿入队，发布出队。替代上游 cheat-on-content 的 cheat-shoot（"拍了"）。触发词："定稿"/"定稿 X"/"排进队列"/"queued"/"这条写好了"。
argument-hint: <drafts-path-or-id> [— planned: <ISO>]
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# /cheatx-queue — 定稿入队

把一条帖子从"已预测的草稿"推进到"定稿、排队待发"：
1. 建 `posts/<同名>/`
2. 问"要发的文本和草稿一致吗？"→ 写 `final.md`
3. 归一化字符差异 ≥ `V2_TRIGGER_THRESHOLD` → 调 `/cheatx-predict — mode: v2` 追加 `## 预测 v2`
4. 加进 `state.queue`，队列 +1

cheatx-queue **不写预测内容**——只负责检测改稿、派发 v2、维护队列。

为什么单独一步：
- 队列要区分"写好排着"和"已发出"——一次写 5 条、分两天发很常见
- 发之前最后一刻改稿是常态。把差异显式化，v2 在发布前重判；草稿 vs 定稿的差异本身就是写法 pattern 的证据
- 定稿文本是发布后"发出的文本和预测的文本是否一致"检查的基准

## Constants

- **REQUIRE_PREDICTION = true**
- **V2_TRIGGER_THRESHOLD = 0.30**——用 [`tools/diff_pct.py`](../../tools/diff_pct.py)（归一化后字符级 Levenshtein / 较长文本长度）
- 回复（`form: reply`）**不进队列**：回复要趁早发，排队没有意义。reply 预测后直接发，然后 `/cheatx-publish`

## Workflow

### Phase 0：解析 + 验证

1. 路径形态：完整路径 / `<date>_<id>_<short>` / `<id>` → glob `drafts/*_<id>_*.md`
2. `drafts/<同名>.md` 存在
3. `predictions/<同名>.md` 存在且含 `## 预测` 段
   - 不存在 → **拒绝**："先 `启动预测` / `快押`。定稿后才写预测，判断会被'这条我已经满意了'带偏"
4. 形态是 reply → 提示"回复不用排队，发完直接 `已发 <链接>`"，退出

### Phase 1：查重

`state.queue` 已有这条 → "已经在队列里（N 小时前入队）。要更新定稿文本，还是已经发了？"

### Phase 2：建目录 + 确认定稿

建 `posts/<同名>/`，问：

```
「<短名>」要发的文本和 drafts/<…>.md 一样吗？
a) 一样
b) 改了——把最终文本给我（粘贴或文件路径）
c) 基本是另一条了 → 走 _redo：drafts/<…>_redo.md 重新预测，原预测留档
```

### Phase 3：写 final.md（+ 可能的 v2）

**a**：复制草稿 → `posts/<同名>/final.md`；`final_consistency = consistent`

**b**：
1. 用户文本写入 `final.md`
2. 算差异：
   ```bash
   python <cheat-on-x>/tools/posted_text_check.py drafts/<同名>.md posts/<同名>/final.md
   ```
   （先去掉 frontmatter、上下文段、thread 编号，再算归一化字符差异；底层是 `tools/diff_pct.py`）
   （python 不可用 → 退回行级 diff 并提示可能偏高）
3. `diff ≥ 30%` → 调 `/cheatx-predict — mode: v2 — prediction-file: predictions/<同名>.md`，输入 `posts/<同名>/final.md`
4. `diff < 30%` → 问"只改了 N%，要重判吗？默认不重判，v1 有效"
5. 改了形态（单帖改成 thread、加了配图、加了外链）→ 不管差异多少都建议 v2，因为协变量变了

**c**：不写 final.md，提示 `_redo` 流程，退出。

### Phase 4：state

```json
{
  "queue": [
    {
      "post_folder": "posts/2026-11-12_a3f2c1d4e5b6_ai写作清单/",
      "prediction_file": "predictions/2026-11-12_a3f2c1d4e5b6_ai写作清单.md",
      "drafts_path": "drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md",
      "queued_at": "<ISO>",
      "planned_at": "<ISO 或 null>",
      "final_consistency": "consistent | modified",
      "final_diff_pct": 12,
      "v2_prediction_written": false,
      "final_hash_at_queue": "sha256:<12>"
    }
  ]
}
```

`planned_at`：用户说了打算几点发就记；`/cheatx-recommend` 会按发帖间隔建议时间。

### Phase 5：输出队列状态

按 [cadence-protocol.md](../../shared-references/cadence-protocol.md)：

```
✅ 已入队：posts/2026-11-12_a3f2c1d4e5b6_ai写作清单/
   预测：predictions/…（v1 有效 / v2 已追加）

📦 队列 3 条 ≈ 1 天（🟢）· 今天已发 1 / 目标 3
   建议发布时间：21:00（距上一条主帖 ≥ 2 小时）

发出去后说："已发 https://x.com/…/status/…"
```

颜色变化时高亮（🟢→🔵："队列够发 N 天了，先发"）。

## Key Rules

1. 不写预测内容——v2 由 cheatx-predict 写
2. 必须先有预测
3. `final.md` 写完不再改；要改就重新 `定稿`（会重算差异）
4. 队列实时：每次 queue / publish 都重算
5. 支持连续登记多条

## Refusals

- 「定稿了，但我没预测过」 → 拒绝，先预测
- 「改稿了，直接覆盖 v1，别留 v2」 → 拒绝。v1 是档案
- 「回复也排进队列」 → 不需要，回复直接发

## Integration

- 上游：`/cheatx-predict`
- 下游：`/cheatx-publish` 发布时移出队列，并用 `final.md` 做发出文本一致性检查
- `/cheatx-status`、`/cheatx-recommend`、SessionStart hook 读 `state.queue`
