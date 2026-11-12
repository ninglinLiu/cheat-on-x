---
name: cheatx-seed
description: 和用户聊选题，默认一次一个：用户给一件经历 / 一个观察 / 一个方向，Claude 深挖出一个具体角度，选形态（单帖 / thread / 长帖 / 引用 / 回复），写一份带 frontmatter 的草稿到 drafts/。完全没想法时才调热点源。可选 batch 模式一次出 N 条。触发词："找选题"/"不知道发什么"/"帮我写一条"/"我想发一条关于 X 的"/"seed"/"batch 5"。
argument-hint: "[— batch: N] [— sources: <comma-separated>]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheatx-seed — 选题对话（默认）/ 批量（可选）

核心是**跟用户聊选题**，不是机械 brainstorm。在 X 上，FT（关注转化）和 NF（圈层契合）最好的来源是你自己的一手经验——AI 编不出来。Claude 的角色：听用户讲 → 提炼角度 → 选形态 → 写一份草稿。

## 三种 Mode（自动识别）

```
Mode A — 用户给了具体经历 / 话题（最常见）
  "我今天把 AI 写作提示词清理了一遍，删了一大半"
  → 深挖：哪个瞬间让你决定删？删掉的有什么共同点？
  → 收敛到一个角度 → 提议形态 → 用户认可 → 写 1 份草稿

Mode B — 只有方向
  "想多发点 AI 工具的"
  → "最近哪件具体的事让你想发这个？" → 回到 Mode A

Mode C — 完全没想法
  "不知道发什么"
  → 按 data-source-routing 拉热点 / 读候选池 / 读你的历史高档帖子 → 只提 1 个角度 → 回到 Mode A 深挖

Batch — "batch 5"
  → 一次出 N 个候选 + N 份草稿（适合想把未来两天排满的时候）
```

AI **不主动抛开放问题**——用户给一句话再深挖；一次一个，batch 是例外。

## Constants

- **MAX_DEEP_DIVE_TURNS = 4**——Mode A 最多追问 4 轮
- **MODE_B_MAX_REPROBE_TURNS = 2**——超过转 Mode C
- **WITH_DRAFT = yes**——角度确认后直接写草稿；用户说"我自己写"就跳过
- **DRAFT_LENGTH**（按形态）：
  - `single` / `quote` / `reply`：≤ 280 加权字符（中文按 2 计，约 140 字）；Premium 用户写长帖要明确改成 `long`
  - `thread`：5-10 条，每条 ≤ 280 加权字符，第一条独立成立
  - `long`：800-2500 字，折叠前一段 ≤ 280 加权字符
  - `article`：1500-5000 字 + 标题 + 封面建议
- **HUMANIZE_DRAFT = on**——装了 humanizer 类 skill 就过一遍，去掉 AI 腔（破折号滥用、三段排比、空泛形容词）。X 读者对 AI 腔很敏感，这是 NR 风险

## Inputs

| 来源 | 用途 |
|---|---|
| `.cheatx-state.json` | `forms_enabled`、`primary_language`、`x_premium`、`calibration_samples` |
| `rubric_notes.md` | 粗打分 |
| `post_patterns.md` | 写法（第一行、thread 结构、手机节奏） |
| `samples/<自己 handle>/` | init 时导入的历史帖子（高档那几条最有参考价值） |
| `benchmark.md` + `samples/<对标>/` | 对标方向感 |
| `audience.md` | 读者画像（confidence 🟡 以上才当检验视角；**不进打分**） |
| `candidates.md` | Mode C / batch 的素材 |

## Workflow

### Phase 0：加载 context

1. 没有 state → 先 `/cheatx-init`
2. 读 rubric、post_patterns
3. **来源 A（你自己）**：`samples/<handle>/` 的历史 + 已复盘的 predictions（只看结论倍数和维度，不需要细节）
4. **来源 B（对标）**：benchmark.md
5. **读者镜子**：audience.md

谁主导：你自己的样本 ≥ 15 条或已明显走出对标路线 → A 主导；否则 B 主导；两者都空 → 只靠用户输入，并建议先 `/cheatx-learn-from`。

### Phase 1：分流

- 含具体名词 + 经历 / 情绪 → Mode A（如果是时事，Phase 2A.5）
- 只有方向词 → Mode B（**不调**热点工具）
- "不知道" / "帮我想" → Mode C
- `batch N` → Batch
- 只说了"找选题" → 问一个入口问题：

```
今天想发什么？
- 有想说的事 → 直接说（"我今天……"）
- 有方向 → 说方向，我问你为什么
- 完全没想法 → 说"帮我想"，我看看热点和你的候选池
- 想一次排几条 → "batch 5"
```

### Phase 2A：Mode A 深挖

追问围绕三件事（最多 4 轮）：
1. **具体瞬间**：哪件事、哪个数字、哪句话让你想发？（→ HK 的素材）
2. **你独有的**：这件事里只有你知道 / 只有你做过的部分？（→ FT、SV）
3. **读者会接什么**：读的人会想补充、反驳、还是收藏？（→ RP / RS / SV，决定形态）

收敛后提议：

```
角度：删掉的 7 个提示词各自为什么没用——比"推荐 3 个好用的"更少见，也更可信
形态：thread（7 条，每条一个删掉的理由；最后一条是留下的 3 个）
第一条草案：「我用 AI 写作半年，删掉了 7 个提示词。留下的 3 个每天在用。」
预计强项：SV、HK；风险：RP 偏低（清单不太引发讨论）→ 结尾留一个"你会删哪个"
要这个角度吗？
```

### Phase 2A.5：时事话题

用户讲的是时事 → 问"要不要看看 X 上现在怎么讨论这个？"同意才调 x-trends / 搜索；不同意直接写。时事帖考虑 `quote` 形态（引用一条最核心的原帖 + 你的一手判断）。

### Phase 2B：Mode B

单问一次"最近哪件具体的事让你想发这个方向？"——最多 2 轮，还是没有具体的事 → Mode C。

### Phase 2C：Mode C

1. 按 [data-source-routing.md](../../shared-references/data-source-routing.md) 调热点（失败降级到 manual-paste）
2. 同时看候选池 tier1 和你历史里高档帖子的话题
3. **只提 1 个角度**，并问"这件事你有没有一手经历？"——没有一手角度的热点，FT 和 NF 通常都低，提醒用户
4. 用户有经历 → 回到 Mode A；没有 → 换一个，最多 3 次，然后建议"今天发一条回复也可以"

### Phase 2D：Batch

1. 一次性问：方向、这批要几条、形态比例
2. 出 2N 个候选（每个一句话 + 建议形态 + 粗打分），用户挑 N 个
3. 每个写一份草稿
4. 候选全部进 candidates.md（没挑中的标 tier2）

### Phase 3：落候选池

按 [candidate-schema.md](../../shared-references/candidate-schema.md) 算 id，写进 candidates.md（`source: idea:self` / `trend:…`），`form_hint` 填选定形态。

### Phase 4：写草稿

文件：`drafts/<今天>_<12 位 id>_<3-8 字短名>.md`，`<id>` = 草稿首次落盘内容的 sha256 前 12 位。

```markdown
---
form: thread
media: text
has_link: no
quote_target: n/a
---

> ⚠️ AI 草稿——发之前用你自己的话改一遍。一字不改直接发，读者能看出来，也测不到你自己的写法。

1/ 我用 AI 写作半年，删掉了 7 个提示词。留下的 3 个每天在用。

2/ ……
```

- 语言按 `primary_language`
- 写法按 `post_patterns.md`：第一行独立成立；一行一个意思；不要"欢迎评论区告诉我"类诱导话术
- 单帖 / 每条 thread 超 280 加权字符 → 自己先拆或压缩
- quote / reply：在文末加"## 被引用 / 被回复的帖子（上下文，不打分）"贴原帖正文
- 有外链：标 `has_link: yes`；不要为了躲"外链降权"把链接塞进第一条回复——这条规律是否成立，让你自己的数据说话

### Phase 4.5：自检

1. 长度符合形态
2. 第一行能不能独立成立（遮住后面只看第一行，还知道这条在说什么吗？）
3. 去 AI 腔（`HUMANIZE_DRAFT`）
4. 有没有诱导话术 / 标题党（会推高 NR）

### Phase 5：下一步

```
✅ 草稿：drafts/2026-11-12_a3f2c1d4e5b6_ai写作清单.md（thread，7 条）

下一步：
- 用你的话改一遍（尤其第一条）
- 想看分数 → "打分这条 drafts/…"
- 改好了 → "启动预测 drafts/…"
- 再来一条？
```

## Key Rules

1. 一次一个（batch 除外）
2. 不凭空编经历——用户没说过的事不能写进草稿当"我的经历"
3. 草稿带 frontmatter，形态明确
4. 内省阶段不调热点
5. 草稿顶部的"AI 草稿"提醒保留

## Refusals

- 「直接给我 20 个选题」 → 引导 batch（最多 10）或一次一个
- 「帮我编一个我的经历」 → 拒绝。写成"我"的经历必须是用户真实的；可以写成观察或假设
- 「写成互动诱导模板（转发抽奖 / 评论区扣 1）」 → 拒绝，这是平台操纵，也会推高 NR
- 「写完直接帮我发」 → 不发。发布是你的动作；先预测

## Integration

- 上游：`/cheatx-recommend` 推了题 → "帮我写第 1 条"进来
- 下游：`/cheatx-score` / `/cheatx-predict`
- 写入 `candidates.md`、`drafts/`
