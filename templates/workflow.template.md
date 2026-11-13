# 工作流速查（cheat-on-x）

> `/cheatx-init` 在你的项目根创建的速查。完整规范在 cheat-on-x 的 `SKILL.md` 和 `shared-references/`。

---

## 一条帖子的一生

```
找选题 → /cheatx-seed（或你自己有想法）
  ↓
草稿 → drafts/<日期>_<id>_<短名>.md
  ↓
（可选）"打分这条 drafts/..." → 看 8 维分，不写文件，可反复改
  ↓
"启动预测 drafts/..."（完整）/ "快押 drafts/..."（日常短帖）/ "批量预测 drafts/"
  → predictions/<同名>.md，## 预测 v1 段被 hook 锁死
  ↓
"定稿 drafts/..." → posts/<同名>/final.md，队列 +1
  └─ 定稿和草稿差 ≥30% → 自动追加 ## 预测 v2（仍在发布前）
  ↓
在 X 上发出去 → "已发 https://x.com/<你>/status/<id>"
  → header 补发布信息，队列 -1，复盘到期时间 = 发布 + 48h（长帖 / Article 7 天）
  ⚠️ 从这一刻起别再改这条的预测
  ↓
48h 后 → 在 x.com 打开自己主页，用油猴脚本导出 CSV 到 imports/
  → "复盘到期的"（agent 用 `import_csv.py find` 自己去下载文件夹找文件；或单条 "复盘 predictions/..."）
  → posts/<id>/report.md + 预测文件 ## 复盘 段 + rubric-memo.md 观察
  ↓
连续同向偏差 / 校准池够了 → /cheatx-bump
```

---

## 触发词速查

| 想做什么 | 说 | 写文件？ |
|---|---|---|
| 找选题 / 写草稿 | "找选题" / "帮我写 5 条" | drafts/ |
| 看分数（探索） | "打分这条 drafts/..." | 否 |
| 正式预测 | "启动预测 drafts/..." | predictions/ |
| 日常快押 | "快押 drafts/..." | predictions/ |
| 一次预测多条 | "批量预测 drafts/" | predictions/ × N |
| 定稿入队 | "定稿 drafts/..." | posts/ |
| 发布登记 | "已发 https://x.com/..." | 预测 header |
| 单条复盘 | "复盘 predictions/..." | 复盘段 + report.md |
| 批量复盘 | "复盘到期的 imports/x.csv" | 同上 × N |
| 看板 | "X 状态" | STATUS.md |
| 今天发什么 | "推荐今天发什么" | 否 |
| 抓热点 | "抓 X 热点" | candidates.md |
| 对标 | "导入对标账号 @xxx" | benchmark.md / samples/ |
| 读者画像 | "受众画像" | audience.md |
| 升级 rubric | "升级 rubric" | rubric_notes.md / rubric-memo.md |

> **score vs predict**：score 是探索，没副作用；predict 是承诺，写完锁死。

---

## 数据怎么回来

| 路线 | 怎么做 | 成本 |
|---|---|---|
| **油猴脚本（默认）** | 装 `cheatx-exporter.user.js`，在 x.com 浏览自己主页 / 帖子页 / 分析页，点"导出" | 免费 |
| X Analytics 导出 | Premium 账号在 Analytics 页面导出 CSV | 订阅内含 |
| 其他油猴脚本 / 插件的 CSV | 放进 imports/，`x-csv-import inspect` 看列名，必要时 `--map` | 免费 |
| X API（可选） | `.cheatx-secrets.json` 放 Bearer Token | 按量计费，调用前会估价 |
| 手动粘贴 | 打开帖子把数字和回复粘过来 | 免费，慢 |

**复盘必须带回复**：至少 10 条（带赞数）。只有数字的复盘只能告诉你"多少"，告诉不了你"为什么"。

---

## 三条不能破的规矩

1. **先预测再发**。发出去几分钟就有计数——没预测就发的帖子只能记 reconstructed，不进校准池
2. **预测段不改**。hook 会拦；真要重做就 `_redo.md`
3. **rubric_notes.md 不写具体帖子和数字**。那些写 rubric-memo.md

---

## 文件

| 文件 | 干嘛的 | blind 打分能读？ |
|---|---|---|
| `rubric_notes.md` | 当前规则 | ✅ |
| `rubric-memo.md` | 观察 + 升级 Memo（带数据） | ❌ |
| `post_patterns.md` | 写法 pattern | ❌ |
| `benchmark.md` | 对标账号 | ❌ |
| `audience.md` | 读者画像 | ❌ |
| `candidates.md` | 选题池 | — |
| `STATUS.md` | 看板 | ❌ |
| `.cheatx-state.json` | 状态 | ❌ |
