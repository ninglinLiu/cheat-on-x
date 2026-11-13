# cheat-on-x — agent 入口

- **用户让你启动 / 安装 / 使用 cheat-on-x**（"启动""用这个""start""set this up"）→ 按 [START.md](START.md) 做。用户不需要懂任何命令。
- **用户已经在一个 cheat-on-x 工作区里**（目录里有 `.cheatx-state.json`）→ 读 [SKILL.md](SKILL.md) 的「托管模式」一节照做。
- **你在开发、修改这个仓库本身** → 见 [SKILL.md](SKILL.md) 末尾「给开发者」。改完跑测试：

  ```bash
  python -m unittest discover -s adapters/perf-data/x-csv-import -p "test_*.py"
  python -m unittest discover -s adapters/perf-data/x-api -p "test_*.py"
  python -m unittest discover -s tools -p "test_*.py"
  python -m unittest discover -s hooks -p "test_*.py"
  node --test userscripts/test/exporter.test.js
  ```

这个目录是工具包源码，**不是**用户的发帖工作区。不要在这里建 `drafts/`、`predictions/` 或 `.cheatx-state.json`。
