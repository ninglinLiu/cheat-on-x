# Blind Prediction Protocol（盲预测协议）

被这些子 skill 引用：`cheatx-predict`、`cheatx-retro`、`cheatx-publish`、主 SKILL.md。

项目原则 #1 的完整规范。任何子 skill 写预测前都必须执行本协议。

---

## 核心定义

**盲预测**：在预测者（人或模型）看到这条帖子发布后任何真实表现数据**之前**完成的预测。

预测写入 `predictions/*.md` 的 `## 预测` 段后即 **immutable**——只能在文件末尾追加 `## 复盘` 段。

### X 的特殊风险

X 帖子发出去几秒就开始显示浏览数，回复几分钟内就来。视频平台"发了再补预测、只要没看后台"在 X 上几乎不成立——**你一定会看到**。

所以 X 版规则比上游更硬：**预测必须在点"发布"之前落盘。** 已经发出去的帖子，默认只能记 reconstructed。

---

## "见过数据"的边界

| 信息 | 破坏盲度？ |
|---|---|
| 这条帖子的浏览数 / 赞 / 转 / 引用 / 回复 / 收藏 | ✗ 破坏 |
| 这条帖子下的回复内容、引用内容 | ✗ 破坏 |
| 这条帖子被谁转发了 | ✗ 破坏 |
| 发出后自己刷到它在时间线里的样子（带计数） | ✗ 破坏 |
| 这条帖子的分析页 / 导出 CSV 里它的那一行 | ✗ 破坏 |
| 同时段**别人**帖子的表现 | ○ 不破坏 |
| 你自己**过去**帖子的表现（锚点对比要用） | ○ 不破坏 |
| 发布前的草稿 / 定稿 | ○ 不破坏（这是输入） |
| 发布前给朋友看、朋友说"这条会火" | △ 不算数据，但在预测里标注 |

**判断捷径**：这条信息是不是只有发布之后才拿得到？是 → 算数据。

---

## 预测前必须自检

`cheatx-predict` 启动时（批量模式对每条都查）：

1. **帖子已发布？**
   - 未发 → 通过
   - 已发 → 默认按 reconstructed 处理（见下）。唯一例外：发出 ≤ 10 分钟、用户明确确认"没看任何计数、没看回复" → 允许写，header 标 `published_before_prediction: true` + `blind_status: confirmed_no_data_seen`，复盘时该样本降权 0.5
2. **对话里出现过这条帖子的任何数字或回复？** 有 → reconstructed
3. **CSV / API 导入时机**：同一会话里如果刚导入过包含这条帖子的 CSV（比如批量复盘时导入的文件恰好也包含今天刚发的帖子）→ 这条已经不盲

`BLIND_CHECK=strict`（默认）：命中即拒绝写预测，改走 reconstructed。
`BLIND_CHECK=lenient`：只警告 + 强制在 header 标 `**Reconstructed retrospective — NOT a blind prediction**`。仅用于演练。

### Reconstructed retrospective

已见数据的帖子仍然可以分析，但：
- 文件名 `<short>_redo.md`
- header 第一行 `**Reconstructed retrospective — NOT a blind prediction**`
- **不计入** `calibration_samples`，不进 bump 校准池
- 可以作为观察写进 `rubric-memo.md`（标 reconstructed）

---

## 数据导入时保持盲度

CSV 导出和 API 都会一次带回很多条帖子的数据，包括还没到复盘时间的、甚至刚发的。规则：

- `x-csv-import` 的 `due` / `post` 子命令只给**指定的、已到期的**帖子写 report.md，并且只在终端打印这些帖子的数字
- 导入器**不在对话里打印**未到期帖子的指标；`inspect` 子命令只打印列名和行数
- 发布登记时（`cheatx-publish`）读取发出的正文做一致性检查，**只取正文列**，不打印任何计数
- x-api 的 `text` 子命令只请求正文字段，不请求 `public_metrics`

---

## Immutable 的工程边界

- `hooks/prediction-immutability.sh` 在 PreToolUse(Edit|Write) 检查 `predictions/` 下的文件
- 改动命中 `## 预测…` 段 → **exit 2**（Claude Code 只在退出码 2 时真正拦截工具调用）
- 改 header（第一个 `##` 之前）、追加 `## 复盘` → 放行
- 对已存在的预测文件用 Write 整体覆盖 → 拦截

**不允许绕开的请求**：
- "把预测写准一点" → 拒绝；要重做建 `_redo.md`
- "概率写错了 0.5%" → 复盘段追加更正说明
- "我前面没考虑 RP=4，重打" → 同上

唯一合法 bypass：纯 markdown 排版错误，用户手动设 `CHEATX_BYPASS_IMMUTABILITY=1` 单次执行，git history 留痕。

> hook 拦不住 Bash 里的 `sed -i` 之类改文件——这是君子协定的部分。`cheatx-retro` 的前后哈希校验是第二道防线。

---

## 文件名约定（三处一致）

```
drafts/<date>_<id>_<short>.md
predictions/<date>_<id>_<short>.md
posts/<date>_<id>_<short>/
```

- `<date>` 草稿首次落盘日；`<id>` 草稿首次落盘内容 sha256 前 12 位，之后不变；`<short>` 3-8 字

---

## 子 skill 检查清单

`cheatx-predict`：执行上面的自检 → 通过才写文件。

`cheatx-retro`：
1. 读目标预测文件，在内存里 cache 所有 `## 预测…` 段
2. 拿数据 → 追加 `## 复盘`
3. 写完重新读文件，所有预测段的合并哈希必须等于第 1 步 → 不等就报错并回滚

主 SKILL.md：用户要求改预测 → 直接拒绝，引导 `_redo.md`。

---

## 异常状态

| 场景 | 处理 |
|---|---|
| 预测段被外部手改 | 不自动回滚。复盘段追加 `**Integrity warning**: 预测段于 <时间> 被外部修改`，样本不进 bump 校准池 |
| 预测文件丢失 | git log 找回；找不到就在 `rubric-memo.md` 记"<id> 预测文件遗失" |
| 发了但忘了预测 | reconstructed，不计入校准池 |
| 发出正文和预测稿差 ≥ 30% | 复盘段 Integrity warning，bump 时降权（详见 prediction-anatomy.md） |

---

## Why

盲预测是校准循环的**唯一信号源**。预测段一旦能事后修改，所有"哪个维度被验证 / 推翻"都失去基线。

预测精度可以靠 rubric 升级慢慢提高；预测可信度一旦破坏不可恢复——所以 immutability 是 hook 层强制，不是君子协定。
