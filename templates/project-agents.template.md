<!-- cheat-on-x:begin（由 cheatx-init 写入；要改行为请改 cheat-on-x 的 SKILL.md，这段可以整段删掉来退出托管模式） -->
# 这是一个 cheat-on-x 项目

这个目录是 [HANDLE] 的 X（Twitter）发帖工作区，用 cheat-on-x 做"发之前押注 → 发 → 48 小时后对答案 → 修正判断"的循环。

**工具包位置**：`[CHEATX-HOME]`（下面写作 `<cheat-on-x>`）

## 每次会话开始

1. 读 `<cheat-on-x>/SKILL.md`，按其中 **「托管模式」** 一节工作——本会话里用户说的每句话，都先判断它和发帖循环有什么关系。
2. 跑 `python <cheat-on-x>/hooks/session_start.py .`（Claude Code 的 SessionStart hook 已经跑过就不用再跑），用一两句话告诉用户现在最要紧的一件事，并给出建议。用户同意再动手。

## 用户不需要知道的东西

用户不需要记任何命令、触发词或文件路径。草稿存哪、文件叫什么、什么时候该押注、什么时候该复盘——都是你的事。用户只需要说人话：贴草稿、说"我要发了"、说"发了"、说"数据怎么样"。

## 三条不能破的规矩（细节见 `<cheat-on-x>/SKILL.md`）

1. **先押注再发。**用户说要发了，先写预测、锁定，再让用户发。发出去之后补的预测不算数。
2. **复盘窗口到之前，不看也不说那条帖子的数据。**导入数据只用 `<cheat-on-x>/adapters/perf-data/x-csv-import/import_csv.py` 的 `due` / `find`，不要自己打开 CSV 读数字。
3. **`predictions/` 里的预测段写完不改。**要改只能追加 `## 预测 v2` 或复盘段。

与发帖无关的问题照常回答，不要硬往这套工具上套。
<!-- cheat-on-x:end -->
