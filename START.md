# 启动 cheat-on-x（写给 agent 看）

> For agents: the user handed you this repository and said "start" / "启动" / "use this". Follow the steps below. Talk to the user in their language. They should never need to learn a command, a trigger word, or a file path.

用户把这个仓库的链接发给你，说"启动"、"用这个"、"帮我装上"——照下面 5 步做。原则：

- **只问必须问的。**能自己判断的（装在哪、文件叫什么、用哪种模式）就自己定，做完用一句话告诉用户。
- **每一步失败都照实说**，不要写"✅ 完成"掩盖。
- 改用户电脑上的东西（装 skill、建目录）之前，用一句话说明要做什么；用户说了"启动 / 帮我装"就算同意，不必再逐项确认。

---

## 第 0 步：你能不能跑这套工具

完整循环要求你能**读写本地文件、执行命令**（Claude Code、Codex、Cursor、Gemini CLI 这类 agent 都可以）。

做不到（比如你是网页聊天框，没有文件系统）→ 直接告诉用户：

```
我这里存不了文件，没法替你押注存档、48 小时后对答案——那是这套工具的核心。
想要完整功能，请在 Claude Code / Codex / Cursor 这类能操作电脑的 agent 里打开它。

现在我可以先做轻量版：你贴草稿，我按 X 推荐算法的 8 个维度给你打分、指出最该改的地方。
```

然后读 `starter-rubrics/x-post-zero.md`，按它给用户贴的草稿打分。不要假装写了预测。

## 第 1 步：拿到工具包

下文 `<cheat-on-x>` 指工具包所在目录。

1. 已经有了就直接用：当前目录根下的 `SKILL.md` 写着 `name: cheat-on-x`，或者 `~/cheat-on-x/SKILL.md` 存在。可以顺手 `git -C <cheat-on-x> pull --ff-only`，失败就算了。
2. 没有 → `git clone <用户给的仓库链接> ~/cheat-on-x`。没有 git → 下载 zip 解压到 `~/cheat-on-x`。
3. 确认有 Python 3（`python --version` 或 `python3 --version`）。导入数据和几个检查工具要用它；没有就告诉用户装一个，其他步骤照常继续。

## 第 2 步：注册 skill（让触发词和斜杠命令生效）

| 你是 | 做什么 |
|---|---|
| Claude Code | `bash <cheat-on-x>/install.sh --yes`（Windows 上建不了软链接时加 `--copy`）。注册 1 个入口 skill + 15 个 `/cheatx-*` 斜杠命令 |
| Codex | `bash <cheat-on-x>/install.sh --codex --yes` |
| 其他 agent | 跳过。第 4 步会在工作区写 `AGENTS.md`，你下次在那里打开就会读到 |

新注册的 skill 一般要**下一个会话**才出现在列表里。这不影响当前会话：你直接读 `<cheat-on-x>` 里的文件照做就行。

## 第 3 步：选工作区

工作区是用户的 X 发帖目录（草稿、预测、复盘都存这里），**不是**工具包目录。

1. 当前目录已有 `.cheatx-state.json` → 已经初始化过，跳到第 5 步。
2. 当前目录是空的，或者用户说"就用这里" → 用当前目录。
3. 其他情况（当前目录是代码仓库、是 `<cheat-on-x>` 本身、是用户主目录）→ 建 `~/x-posts` 作为工作区，告诉用户一句："我把你的发帖工作区建在 `~/x-posts`，以后在这个目录里打开 agent 就行。"

工作区不是当前目录时：本会话里所有文件操作都加上工作区路径前缀，命令里的 `--project .` 换成工作区路径。Claude Code 的项目 hook 只在**从工作区打开的会话**里生效，所以本会话里预测锁不会自动拦截。这一点要告诉用户，并照常遵守规矩。

## 第 4 步：初始化（快速模式）

读 `<cheat-on-x>/skills/cheatx-init/SKILL.md`，按**快速模式**做（默认）：只问 3 个问题，其余用默认值，以后用到时再问。它会在工作区写 `AGENTS.md` 和 `CLAUDE.md`，让以后每个会话自动进入托管模式。

## 第 5 步：进入托管模式

读 `<cheat-on-x>/SKILL.md` 的 **「托管模式」** 一节。从这一刻起，用户在这个对话里说的每句话，你都按那一节判断该接哪个环节。

初始化完的第一句话，照这个意思说（用自己的话，别念稿）：

```
好了。以后你不用记任何命令，正常跟我说就行：
- 写了草稿就直接贴给我，我打分、提修改建议
- 要发了告诉我一声，我先花几秒押个注、锁起来
- 发完把链接给我；48 小时后我提醒你看结果

现在有想发的东西吗？直接贴过来，或者说个主题我帮你起草。
```
