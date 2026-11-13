# Changelog

All notable changes to cheat-on-x are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/); versions follow [SemVer](https://semver.org/lang/zh-CN/).

cheat-on-x is derived from [XBuilderLAB/cheat-on-content](https://github.com/XBuilderLAB/cheat-on-content) at `d88d004`. Upstream's own changelog (its v0.1.0 → 1.4 schema history) lives in the upstream repo and in this repo's git history (`git show d88d004:CHANGELOG.md`).

---

## [0.2.0] — 2026-11-13 — 托管模式：不用学命令

用户反馈：新人不知道草稿要放 `drafts/`，也记不住"启动预测""定稿""复盘到期的"这些说法。这一版让 agent 自己判断每句话该接哪个环节。

### Added

- **一句话启动**：`START.md`（写给 agent 的引导）+ 根目录 `AGENTS.md` / `CLAUDE.md`。把仓库链接丢给 agent 说"启动 cheat-on-x"，它自己装 skill、建工作区（默认 `~/x-posts`）、快速初始化
- **托管模式**（根 `SKILL.md`）：意图表代替触发词表——贴草稿 → 存草稿 + 打分；"要发了" → 先押注锁定再放行，并自动定稿入队；"发了 + 链接" → 登记；"数据怎么样" → 自动找导出文件并复盘。每步结尾一行"下一步"，开场挑最要紧的一件事说
- **工作区 `AGENTS.md` / `CLAUDE.md`**（`templates/project-agents.template.md`）：`cheatx-init` 写入，以后在工作区打开任何 agent 都自动进入托管模式
- **`cheatx-init` 快速模式**（默认）：3 个问题；其余用默认值，记进 `state.deferred_setup`，到用得上时再问（历史 → 第一次押注前；数据路线 → 第一次发布后；对标 → 第一次复盘后）。原 8 问改为 `— mode: full`
- **`import_csv.py find`**：在下载文件夹和 `imports/` 里找最近导出的 CSV，`--copy` 复制进 `imports/`，只输出元数据（保盲）
- **git 留痕**：工作区自动 `git init`（仅本地）；每次押注 / 定稿 / 登记发布后只提交相关文件。没有 hook 的 agent 里，这是预测没被改过的证据
- state 新字段（可选，schema 仍为 x1.0）：`cheatx_home`、`init_mode`、`deferred_setup`、`git_trail`
- 开场报告：升级建议线（校准 ≥ 10 且距上次升级 ≥ 5 条）、推迟的设置项；末尾提示改为托管模式

### Changed

- `install.sh` / `uninstall.sh`：Claude Code 也注册入口 skill `cheat-on-x`（15 个 `/cheatx-*` 斜杠命令保留）；新增 `--yes`（不弹确认，非终端环境下不加 `--yes` 会明确退出而不是卡住）
- `install.sh`：Windows Git Bash 上 `ln -s` 会悄悄复制整个目录（连 `.git`），却仍显示"symlink 模式"。现在先请求原生软链接，拿不到就明确改为复制并说明
- `cheatx-predict`：接受对话里直接贴的正文；托管模式下快押用三四行人话展示；发布信息合成一句话问
- `cheatx-queue`：`— final: same` 跳过"定稿和草稿一样吗"的提问
- `cheatx-publish`：只说"发了"也能按内容找到对应预测；托管模式下第一次发布后提议装油猴脚本
- `cheatx-retro` / `cheatx-learn-from`：不再让用户把 CSV 挪进 `imports/`，改用 `find --copy`
- `cheatx-retro`：识别托管模式写入的 `Integrity Note`
- README（中英）：开头换成"一句话开始"

---

## [0.1.0] — 2026-11-12 — X edition

### Added

- **X-native rubric** — `starter-rubrics/x-post-zero.md` and `x-longform-zero.md`: 8 dimensions (HK / RP / SV / RS / DW / FT / NF + NR penalty). Each maps to the user-action probabilities scored by X's open-sourced Phoenix ranker (xai-org/x-algorithm, Jan 2026). v0 equal-weights the seven positive dimensions; covariates (form, media, link, posting hour, gap, Premium, followers) are recorded on every bet but not scored.
- **Multiplier buckets on per-form baselines** — the baseline is the median of your last 10 retro'd posts of that form. Outcomes are judged on-target within 0.5–2× of the center. Every retro also records a log score for the realized bucket.
- **Quick bets and batch mode** — `cheatx-predict` full / quick / batch / v2. `cheatx-retro due` processes every retro that has come due in one pass.
- **T+48h retro window** (For You drops candidates older than 48h). Long posts and Articles use T+7d.
- **Data layer**
  - `userscripts/cheatx-exporter.user.js` (Tampermonkey / Violentmonkey): read-only tap on x.com's own GraphQL responses. Exports posts, replies, quotes and trends to CSV. No extra requests, no auto-scrolling, nothing uploaded.
  - `adapters/perf-data/x-csv-import/`: stdlib importer for userscript, X Analytics and third-party CSVs (alias table + `--map`). Blind-safe subcommands `inspect / text / post / due / history / trends`.
  - `adapters/perf-data/x-api/` (optional): pay-per-use X API v2 fetcher. It is dry-run by default, prints a cost estimate, and writes canonical CSV that it hands to the importer.
  - `adapters/trend-sources/x-trends.md`.
- **Deterministic tools**: `tools/rank_check.py` (Spearman + bootstrap + per-form regression gate for bumps), `tools/calib_pool.py` (baselines and the bump pool, with a safe formula evaluator and blind re-score back-fill), `tools/leak_check.py` (blind-channel guard for `rubric_notes.md`), `tools/posted_text_check.py` (posted text vs predicted text).
- **Blind scoring of benchmark posts** — `cheatx-learn-from` sends benchmark texts to the blind sub-agent through `.cheatx-cache/blind-input/`, so the "high tier" posts aren't scored by a context that already knows their numbers.
- `hooks/session_start.py`: hour-based due retros, today's posts vs target, queue color.
- Tests: importer 18, x-api 8, tools 14, hooks 16 (real bash), userscript 11 (node), including a cross-language CSV contract test.

### Changed (vs upstream)

- Skills renamed `cheat-*` → `cheatx-*`. `cheat-shoot` ("shot it") became `cheatx-queue` ("finalized, queued"). The state file is now `.cheatx-state.json`, schema `x1.0`, with an independent migration chain.
- Project layout: `scripts/` → `drafts/`, `videos/<id>/script.md` → `posts/<id>/final.md`, `script_patterns.md` → `post_patterns.md`. Added `imports/` (gitignored raw exports).
- Bump validation uses rank correlation with bootstrap stability (threshold 0.80) instead of "≥4/5 samples consistent". Samples are compared as multiples of their own baseline. Exogenous-boost and integrity-warning samples are excluded.
- Observations now live only in `rubric-memo.md`; `rubric_notes.md` holds abstract rules only.

### Fixed (also present upstream)

- **Immutability hook did not block.** Upstream exits `1` on a violation, but Claude Code only blocks a PreToolUse call on exit `2`, so the edit went through. The X hook exits `2`.
- **Immutability hook only locked the `## 预测` heading's own section.** Reasoning, anchors, counterfactuals and the recorded scores stayed editable after the fact. The X hook locks everything from the first `## ` heading up to `## 复盘`.
- **Hook failed open without jq.** The X hook uses Python, falls back to jq + awk, and warns visibly if neither is available.
- **Fallback grep treated blank lines in `old_string` as "match everything".** Blank lines are now dropped from the pattern list.
- **`argument-hint` values containing `: `** broke YAML parsing in several skills. All hints are quoted and every SKILL.md frontmatter is validated with PyYAML.

### Removed

Video / Chinese-platform adapters, whisper, weibo / zhihu trend sources, video starter rubrics, upstream migrations, star-history automation, upstream badges and logo. See [docs/removals.md](docs/removals.md) for the full list and where upstream keeps each item.
