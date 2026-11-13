---
name: cheatx-learn-from
description: 导入 X 对标账号：拿到它 15-30 条帖子的正文和数字（油猴脚本导出 / X API / 手动粘贴）→ 按该账号自己的曝光中位数分高 / 中 / 低档 → 正文交给盲打 sub-agent 打分 → 拆写法 pattern 和定性维度信号 → 写 benchmark.md / samples/ / post_patterns.md / rubric_notes.md（只写抽象方向）。cold-start 账号最早的信号来源。触发词："导入对标账号"/"学 @xxx"/"找对标"/"拆这个号"/"learn from"。
argument-hint: '<@handle> [— append | — replace] [— source: csv|x-api|paste]'
allowed-tools: Bash(*), Read, Write, Edit, Glob, Task, Skill
---

# /cheatx-learn-from — 对标账号导入

刚 init 的账号没有自己的数据，v0 rubric 等于占星。导入一个你想成为的账号的 15-30 条帖子，工具立刻有参照。你自己的校准样本 ≥ 15 条后，对标影响自然淡出，但 benchmark.md 一直保留作对照。

X 上做这件事比视频平台简单：帖子本身就是文字，不需要转录；公开帖子的浏览数就在页面上。

## Constants

- **MIN_SAMPLES = 8**（少于 8 条分不出三档）
- **RECOMMENDED_SAMPLES = 15-30**
- **MAX_SAMPLES_PER_RUN = 50**
- **TIER_RULE**：≥ 2× 该号中位数 = 高；≤ 0.5× = 低；其余中（与 `import_csv.py history` 一致）
- **只看主帖**：默认排除该号的回复（回复的曝光受被回复帖支配，不可比）

## 选对标的建议（用户问"选谁"时给）

- 同领域、同语言
- 比你大 1-2 个量级（太大的号靠存量粉丝，规律不一定适用你）
- 最近 3 个月还在活跃更新
- 形态和你想做的接近（你主要发 thread，就别拿纯图片号对标）

## Workflow

### Phase 0：状态

`benchmark_status`：`none` / `pending` → 继续；`imported` → 问"追加样本 / 换一个账号 / 只看不改"。`— append` / `— replace` 直接走对应路径（replace 时旧 benchmark.md 移到 `benchmark.archived/<handle>_<日期>.md`）。

### Phase 1：取数据（三选一）

**a) 油猴脚本（默认，免费）**

```
1. 在 x.com 打开 @<handle> 的主页
2. 往下滚，滚过 20-40 条（越多越准；滚到你想要的时间范围为止）
3. 想要它的回复区（拆读者反应）：点进几条高浏览的帖子，把回复滚一遍
4. 面板点"导出：全部已记录帖子"。下载完说一声"好了"
```

用户说"好了"→ `python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py find --project . --copy` 自己去下载文件夹找（复制进 `imports/`），不让用户挪文件或报路径。

**b) X API（可选，按量计费）**

```bash
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py history <handle> --limit 30 --samples-dir samples/<handle>          # 预演，看费用
python <cheat-on-x>/adapters/perf-data/x-api/xapi.py history <handle> --limit 30 --samples-dir samples/<handle> --yes    # 用户同意后
```

**c) 手动粘贴**：每条要正文 + 浏览数（+ 赞 / 转 / 回复 / 收藏，能给就给）。

### Phase 2：分档

csv 路线：

```bash
python <cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py history imports/<file>.csv \
  --handle <handle> --samples-dir samples/<handle>
```

输出：该号中位数、按形态中位数、每条的 `ratio_to_median` 和档位；每条正文写到 `samples/<handle>/<status_id>.md`。

手动路线：Claude 自己算中位数和档位，同样写 samples/。

样本 < `MIN_SAMPLES` → 停下："至少 8 条才分得出三档，再滚一点导出一次"。

### Phase 3：你的印象

把三档各挑 2-3 条给用户看正文（**不给数字**，先听直觉），问：

```
这几条里，哪些是"我想写成这样的"，哪些是"我不想写成这样的"？一句话为什么。
```

记录印象。印象和数据档位冲突的样本（数据高但你不喜欢，或反过来）最有价值，Phase 5 单独拆。

### Phase 4：盲打对标样本

拆维度信号时，**不能**让知道结果的主对话来打分——那会把"高档"的帖子自然打高。

1. 每条样本只把**正文**（+ 形态 frontmatter）写到 `.cheatx-cache/blind-input/bench-<handle>-<status_id>.md`——不带浏览数、档位、handle
2. 分批（≤ 10 份一批）交给 `cheatx-score-blind`（契约同 cheatx-predict Phase 2）
3. 拿回维度分后，主对话再把分数和档位对起来
4. 用完删掉 `blind-input/` 里的这些文件

### Phase 5：拆 pattern + 定性信号

**5a 写法 pattern**（按 post_patterns.md 的框架）：第一行类型分布、thread 结构、长度、配图习惯、语气词、结尾方式、发帖时段（如果导出里有时间）。每条 pattern 引用具体样本作证据。

**5b 维度信号（只给定性方向，不给权重）**：
- 高档样本共有哪些维度高？（"高档 5 条里 4 条 SV ≥ 4"）
- 哪些维度高低档无差异？
- 形态差异：该号 thread 的中位数相对单帖是几倍？

**5c 选题方向感**：话题分布、调性。

### Phase 6：用户 review

一次性展示：pattern 列表（带证据）、维度方向、形态倍数、话题分布。"ok" 落盘，或挑刺改。

### Phase 7：落盘

1. **benchmark.md**（模板 [templates/benchmark.template.md](../../templates/benchmark.template.md)）：账号信息、样本表（含曝光、相对中位数倍数、档位、你的印象）、方向信号、话题。`— append` 只追加行并重算中位数
2. **samples/<handle>/**：已在 Phase 2 写好
3. **post_patterns.md** → "对标借鉴"段，每条标 **Imported, untested on my channel**
4. **rubric_notes.md** → "对标账号派生的方向信号"段，**只写抽象方向**：

   ```markdown
   - 高档样本普遍 SV ≥ 4（清单 / 模板类），提示 SV 可能是主驱动
   - RS 在高低档之间无明显差异
   - 对标号的 thread 中位数显著高于其单帖
   ```

   不写 handle、不写帖子名、不写数字。写完跑 `python <cheat-on-x>/tools/leak_check.py rubric_notes.md`，非 0 就改写成更抽象的说法
5. 不改权重——等你自己 ≥ 5 条校准样本、走 `/cheatx-bump`

### Phase 8：state

```json
{ "benchmark_status": "imported", "benchmark_handles": ["<handle>"], "benchmark_sample_count": <N> }
```

并从 `deferred_setup` 里删掉 `benchmark`（如果有）。

## Key Rules

1. 维度分走盲打 sub-agent（Phase 4）
2. 必须问印象
3. 维度信号只定性
4. pattern 默认 untested
5. rubric_notes.md 只进抽象方向，跑 leak_check
6. 只读对方**公开**的帖子；不抓私信、不抓需要登录才看到的别人的分析数据

## Refusals

- 「直接把对标的权重抄过来」 → 拒绝。15-30 条拟合 8 维必然过拟合
- 「帮我把对标账号的帖子改写一下发出去」 → 拒绝。拆的是写法和方向，不是内容；搬运会推高 NR，也是抄袭
- 「批量抓 10 个账号的全部历史」 → 拒绝，一次一个对标，样本 ≤ 50；需要的话分次 `— append`
- 「少于 8 条也拆吧」 → 拒绝，分不出档

## Integration

- `/cheatx-init` Phase 2.5 选 a 时自动进入
- `/cheatx-seed` 读 benchmark.md 和 samples/ 作方向感
- `/cheatx-status` 在你的数据成为主信号后提示对标淡出
