---
name: cheatx-publish
description: 登记一条帖子已在 X 上发布：从链接解析 status id、把发布信息写进预测文件 header、检查发出的文本和预测时的定稿是否一致（只读正文，不读任何数字）、出队、排复盘到期时间。**不动预测段任何字符。**触发词："已发 https://x.com/..."/"发了"/"posted"/"I shipped"/"刚发完 [链接]"。
argument-hint: '<post-url> [prediction-file]'
allowed-tools: Bash(*), Read, Edit, Glob
---

# /cheatx-publish — 发布登记

把发布元数据补到预测文件 header 与 state。**禁止改预测段**——hook 会拦。

## Overview

```
[已发 https://x.com/me/status/1988…]
  ↓
Phase 0 找到对应预测文件
Phase 1 解析链接 → status id、handle；发布时间
Phase 2 发出文本一致性检查（只取正文）
Phase 3 写 header（第一个 ## 之前）
Phase 4 更新 state：出队、pending_retros（含 due_at）、recent_publishes
Phase 5 提醒 + 下一步
```

## Constants

- **TEXT_CHECK = auto**——有数据源就做发出文本检查；没有就标 `unchecked`
- **MIN_SPACING_MINUTES = 120**（state 里可覆盖）——距上一条主帖不足时提醒
- **MAX_PREDICT_AGE_DAYS = 7**——预测写于 7 天前以上 → 确认"真的是这条？"

## Workflow

### Phase 0：找预测文件

托管模式下用户只说"发了"（没给链接、没指明哪条）也要能接住：按下面的优先级自己找，**用内容跟用户确认**（"是'删掉的 7 个提示词'那条吧？"），不让用户报文件名。没给链接 → 顺口要一下："把链接贴我一下，48 小时后要靠它取数据。"

优先级：
1. 参数给了预测文件路径
2. 链接对应的 status id 已出现在某个预测 header 里 → 已登记过，问是否覆盖
3. `state.queue` 里只有一条 → 就是它（确认一句）
4. 多条 → 列出队列 + 未登记发布的预测（header 没有 `Published at`），让用户选
5. reply：不进队列，从未登记的 reply 预测里选

没有任何预测 → "这条没有预测。要不要建一个 `_redo` reconstructed 记录？它不会进校准池。"

### Phase 1：解析

- 链接：`https://x.com/<handle>/status/<id>` / `twitter.com/...` / `x.com/i/web/status/<id>` → status id、handle
- handle 和 `state.x_handle` 不一致 → 问"这是你的账号吗？"（对标账号的帖子不该登记在这里）
- 发布时间：问一句，默认"现在"；接受"20 分钟前"、"21:03"
- 距上一条主帖：从 `state.recent_publishes` 算分钟数；< `MIN_SPACING_MINUTES` → 提醒一次（不阻止）："距上一条只有 45 分钟，这条可能被作者多样性衰减打折。复盘时会记这个协变量。"

### Phase 2：发出文本一致性（保盲）

目的：确认你发出去的就是你预测的那段文本。

**只读正文，不读、不打印任何计数。**

- 数据源 csv：如果用户手边已有一个刚导出的文件（不常见——刚发的帖子通常还没导出）：
  ```bash
  python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py text imports/<file>.csv --id <status_id>
  ```
- 数据源 x-api：
  ```bash
  python <cheat-on-x>/adapters/perf-data/x-api/xapi.py text <status_id> --project .          # 先预演看费用
  python <cheat-on-x>/adapters/perf-data/x-api/xapi.py text <status_id> --project . --yes    # 用户同意后
  ```
- 都没有 → 请用户把发出的正文复制过来（只要正文），或者标 `unchecked`，复盘时导入器拿到正文再补查

thread：`text` 输出里的 `thread_text` 是首条 + 你自己的后续各条拼起来的全文，用它比；只导出了首条时只比首条，并在 header 写 `same（仅首条）`。

比较对象：`posts/<同名>/final.md`（没有就用草稿）。用 `tools/posted_text_check.py`（会先去掉 frontmatter、"被引用的帖子"上下文段、`1/` 这类编号和短链）：

```bash
python <cheat-on-x>/tools/posted_text_check.py posts/<同名>/final.md --text "<发出的正文>"
```

- < 10% → `same`
- 10-30% → `diff N%`
- ≥ 30% → `diff N% ⚠️`——告诉用户："发出的文本和预测时差了 N%。这条复盘时会带 Integrity warning、bump 时降权。要撤回重发吗？还是接受？"

### Phase 3：写 header

只动第一个 `##` 之前的 metadata 块，用 **Edit**（不是 Write）在 header 末尾追加：

```markdown
**Published at**: 2026-11-12T21:03+08:00
**Status ID**: 1988765432109876543
**URL**: https://x.com/yourhandle/status/1988765432109876543
**Post Folder**: posts/2026-11-12_a3f2c1d4e5b6_ai写作清单/
**Posted Text Check**: same
**Minutes Since Previous Post**: 95
**Retro Due**: 2026-11-14T21:03+08:00
```

- 已有 `Published at` → 问"覆盖吗？"，不静默覆盖
- `posts/<同名>/` 不存在（跳过了定稿）→ 自动建目录、把草稿复制成 `final.md`，header 加 `**Ad Hoc Publish**: true`。托管模式下不提醒用户（定稿是你的事）；斜杠命令模式下提醒"下次先 `定稿`"
- hook 误拦 header 编辑 → 报告问题，**不要绕过 hook**

### Phase 4：state

```json
{
  "queue": "[移除 post_folder 匹配的项]",
  "pending_retros": "[追加 {file, status_id, form, published_at, due_at}]",
  "recent_publishes": "[追加 {at, status_id, form}，只保留最近 30 条]",
  "last_published_at": "<ISO>",
  "last_published_file": "predictions/<…>.md"
}
```

`due_at` = 发布时间 + `retro_window_hours`（`long` / `article` 用 `retro_window_hours_longform`）。

队列里找不到这条 → 提示"它没经过定稿"，不阻塞。

### Phase 5：提醒

```
✅ 已登记：predictions/2026-11-12_a3f2c1d4e5b6_ai写作清单.md
   发布 21:03 · status 1988… · 文本一致性：same

📦 队列 2 条（🟢）· 今天已发 2 / 目标 3

⚠️ 从现在起，这条的浏览数、回复、谁转发了——都别贴给我。
   不小心看到了告诉我，我在复盘段记 integrity warning。

📅 复盘到期：11-14 21:03（T+48h）
   到时在 x.com 打开主页、点开这条滚一遍回复，用油猴脚本"导出：我的帖子 + 回复/引用"，
   然后说"复盘到期的"（文件我会自己去下载文件夹找）
```

**托管模式**下换成人话，三四行：

```
记下了，21:03 发的。11-14 晚上 9 点后可以对答案——到时候你打开 agent 我会提醒你。
这两天它的浏览数先别告诉我。
```

再加一条（每个会话最多一次）：
- `deferred_setup` 含 `data_route` → "48 小时后要拿数据。现在花 1 分钟装个浏览器脚本？装好以后导出数据只要点一下。（也可以用付费的 X API，或者到时候手动抄数字）"。用户选了就按 `cheatx-init` Q6 的映射写 state、给安装步骤（`<cheat-on-x>/userscripts/README.md`），并从 `deferred_setup` 删掉 `data_route`
- 文本一致性 `diff ≥ 30%` 的提醒照常说

`state.git_trail = true` → header 改完后 `git commit -m "publish: <短名>" -- predictions/<同名>.md posts/<同名>/final.md`（规则同 cheatx-predict Phase 6.5）。

## Key Rules

1. 不动预测段
2. 不抓、不看、不打印任何数字——发布登记是元数据动作，数据回收是 cheatx-retro 的事
3. state 字段名固定：`pending_retros` / `recent_publishes` / `last_published_at` 是其他 skill 的契约
4. 重复登记要明示

## Refusals

- 「顺手把预测段也改一下」 → 拒绝，走 `_redo`
- 「顺便看看现在多少浏览了」 → 拒绝。复盘窗口没到，看了就不盲了
- 「链接等会儿补，先记发布时间」 → 允许：`URL` 和 `Status ID` 标 `pending`，复盘前必须补上
- 「跳过 header，直接出队」 → 拒绝。status id 是复盘取数的钥匙

## Integration

- 上游：`/cheatx-predict` → `/cheatx-queue`
- 下游：到 `due_at` 后 `/cheatx-retro`
- `/cheatx-status` 和 SessionStart hook 用 `pending_retros[].due_at` 显示到期复盘，用 `recent_publishes` 显示今日条数
