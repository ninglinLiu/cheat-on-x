# Changelog

All notable changes to cheat-on-x are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/); versions follow [SemVer](https://semver.org/lang/zh-CN/).

cheat-on-x is derived from [XBuilderLAB/cheat-on-content](https://github.com/XBuilderLAB/cheat-on-content) at `d88d004`. Upstream's own changelog (its v0.1.0 → 1.4 schema history) lives in the upstream repo and in this repo's git history (`git show d88d004:CHANGELOG.md`).

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
