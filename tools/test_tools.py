"""Tests for tools/leak_check.py and tools/rank_check.py.

Run:  python -m unittest test_tools.py   (from tools/)
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

import leak_check  # noqa: E402
import rank_check  # noqa: E402

REPO = HERE.parent


class TestLeakCheck(unittest.TestCase):
    def test_starter_rubrics_and_template_are_clean(self):
        for rel in ("starter-rubrics/x-post-zero.md", "starter-rubrics/x-longform-zero.md",
                    "templates/rubric_notes.template.md"):
            hits = leak_check.scan((REPO / rel).read_text(encoding="utf-8"))
            self.assertEqual(hits, [], f"{rel}: {hits}")

    def test_detects_leaks(self):
        bad = [
            "参考 https://x.com/me/status/1988765432109876543",
            "那条 1988765432109876543 很好",
            "提示词清单拿到 2,130 曝光",
            "曝光：2130",
            "实绩证明 SV 很重要",
            "被 @bigaccount 转发",
            "got 12.3K views",
        ]
        for line in bad:
            self.assertTrue(leak_check.scan(line), line)

    def test_allows_rules(self):
        ok = [
            "composite = (HK + RP + SV + RS + DW + FT + NF) / 7 × 2.0 − NR × 0.4",
            "`命中` | 1 – 3× 基线",
            "复盘窗口 T+48h",
            "baseline_guess = max(100, 发帖时粉丝数 × 0.3)",
            "规律 1：清单类 thread 的 SV 常被低估一档",
            "联系 me@example.com",
        ]
        for line in ok:
            self.assertEqual(leak_check.scan(line), [], line)


class TestPostedTextCheck(unittest.TestCase):
    def test_clean_strips_non_content(self):
        import posted_text_check as ptc
        final = ("---\nform: thread\nmedia: image\n---\n\n1/ 我用 AI 写作半年后删掉了 7 个提示词\n\n"
                 "2/ 第一个是……\n\n## 被引用 / 被回复的帖子（上下文，不打分）\n原帖正文")
        posted = "我用 AI 写作半年后删掉了 7 个提示词\n\n第一个是…… https://t.co/abc123"
        self.assertEqual(ptc.clean(final), ptc.clean(posted))

    def test_verdicts(self):
        import posted_text_check as ptc
        self.assertEqual(ptc.verdict(3), "same")
        self.assertEqual(ptc.verdict(15), "diff 15%")
        self.assertTrue(ptc.verdict(45).endswith("⚠️"))


PRED = """# {short} — 预测日志

**Post ID**: {pid}
**Form**: {form}
**Baseline**: {form}=n/a（不足 3 条）→ all={base}（最近 10 条中位数）
**Published at**: 2026-11-{day:02d}T21:00+08:00
**Posted Text Check**: {ptc}

---

## 输入快照

**分数 (v0)**: HK{hk} / RP3 / SV{sv} / RS3 / DW4 / FT4 / NF5 / NR1 → composite=**{comp}**

## 预测 v1

**Bucket**: `命中`
**中枢**: {center}

**概率分布**:
- `退步`（<126）→ 10%
- `持平`（126–420）→ 30%
- **`命中`（420–1,260）→ 40%**
- `小爆`（1,260–4,200）→ 15%
- `大爆`（>4,200）→ 5%

## 推理因素
x
## 锚点对比
x
## 反事实场景
x
## 关键校准假设
x

## 复盘

**复盘时间**: 2026-11-{day2:02d}T21:10+08:00（发布 T+48h）

### 实际数据
- 曝光：**{imp}** → 落在 `{bucket}`（预测 `命中`）；实际 / 中枢 = **x**
- 外生冲击：{exo}
"""


class TestCalibPool(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        specs = [  # form, imp, bucket, exo, ptc, hk, sv
            ("single", "300", "持平", "无", "same", 3, 2),
            ("single", "520", "命中", "无", "same", 4, 3),
            ("single", "1.2K", "命中", "无", "same", 4, 4),
            ("thread", "2,130", "小爆", "无", "same", 4, 5),
            ("single", "9,000", "大爆", "被 @big 转发，疑似主导曝光", "same", 3, 2),
            ("single", "700", "命中", "无", "diff 41% ⚠️", 3, 3),
        ]
        for i, (form, imp, bucket, exo, ptc, hk, sv) in enumerate(specs):
            (self.dir / f"2026-11-{i + 1:02d}_id{i}_p{i}.md").write_text(PRED.format(
                short=f"p{i}", pid=f"id{i}", form=form, base=420, day=i + 1, day2=i + 3, ptc=ptc, hk=hk, sv=sv,
                comp="7.0", center=800, imp=imp, bucket=bucket, exo=exo), encoding="utf-8")
        (self.dir / "2026-11-09_id9_未复盘.md").write_text(
            PRED.format(short="x", pid="id9", form="single", base=420, day=9, day2=11, ptc="same", hk=3, sv=3,
                        comp="6", center=500, imp="1", bucket="命中", exo="无").split("## 复盘")[0]
            + "## 复盘\n\n（待填——复盘窗口到期后跑 `/cheatx-retro`）\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_and_flags(self):
        import calib_pool
        recs = {Path(r["file"]).stem: r for r in calib_pool.load_dir(self.dir)}
        self.assertEqual(recs["2026-11-03_id2_p2"]["impressions"], 1200)
        self.assertEqual(recs["2026-11-04_id3_p3"]["dims"]["SV"], 5)
        self.assertEqual(recs["2026-11-04_id3_p3"]["probs"]["小爆"], 0.15)
        self.assertIn("exogenous", recs["2026-11-05_id4_p4"]["flags"])
        self.assertIn("integrity", recs["2026-11-06_id5_p5"]["flags"])
        self.assertFalse(recs["2026-11-09_id9_未复盘"]["retro"])

    def test_baseline_excludes_flagged(self):
        import calib_pool
        import contextlib
        import io
        import json as _json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            calib_pool.main(["baseline", str(self.dir), "--json"])
        res = _json.loads(buf.getvalue())
        self.assertEqual(res["counts"]["all"], 4)                    # exogenous + integrity excluded
        self.assertEqual(res["baseline_impressions"]["single"], 520)  # median of 300, 520, 1200
        self.assertIsNone(res["baseline_impressions"]["thread"])      # < 3 samples

    def test_pool_with_formulas(self):
        import calib_pool
        out = self.dir / "pool.csv"
        calib_pool.main(["pool", str(self.dir), "--out", str(out),
                         "--formula-old", "(HK + RP + SV + RS + DW + FT + NF) / 7 * 2 - NR * 0.4",
                         "--formula-new", "(HK + RP + SV*2 + RS + DW + FT + NF) / 8 * 2 - NR * 0.4"])
        import csv as _csv
        with open(out, encoding="utf-8") as fh:
            rows = list(_csv.DictReader(fh))
        self.assertEqual(len(rows), 4)
        thread = next(r for r in rows if r["form"] == "thread")
        self.assertAlmostEqual(float(thread["composite_old"]), 7.6, places=3)
        self.assertAlmostEqual(float(thread["outcome_ratio"]), 2130 / 420, places=3)
        self.assertAlmostEqual(float(thread["log_score"]), round(__import__("math").log(0.15), 4))

    def test_rescores_backfill_new_dimension(self):
        import calib_pool
        import json as _json
        side = self.dir / "sidecars"
        side.mkdir()
        (side / "bump-1.json").write_text(_json.dumps({"results": [
            {"draft_path": "drafts/2026-11-04_id3_p3.md", "refusal": None,
             "dimensions": {"SV": {"score": 4, "confidence": "high", "reason": "x"}},
             "candidate_dimensions": {"TM": {"score": 2, "confidence": "low", "reason": "y"}}},
            {"draft_path": "posts/2026-11-01_id0_p0/final.md", "refusal": None,
             "dimensions": {}, "candidate_dimensions": {"TM": {"score": 5, "confidence": "low", "reason": "z"}}},
        ]}), encoding="utf-8")
        out = self.dir / "pool2.csv"
        calib_pool.main(["pool", str(self.dir), "--out", str(out), "--rescores", str(side),
                         "--formula-new", "HK + SV + TM"])
        import csv as _csv
        with open(out, encoding="utf-8") as fh:
            rows = {Path(r["file"]).stem: r for r in _csv.DictReader(fh)}
        self.assertEqual(float(rows["2026-11-04_id3_p3"]["composite_new"]), 4 + 4 + 2)   # SV overridden 5→4
        self.assertEqual(float(rows["2026-11-01_id0_p0"]["composite_new"]), 3 + 2 + 5)
        self.assertEqual(rows["2026-11-02_id1_p1"]["composite_new"], "")                 # TM missing → needs backfill
        self.assertIn("rescored", rows["2026-11-04_id3_p3"]["flags"])

    def test_formula_is_safe(self):
        import calib_pool
        self.assertEqual(calib_pool.eval_formula("max(HK, 2) * 2", {"HK": 1}), 4.0)
        self.assertIsNone(calib_pool.eval_formula("HK + TM", {"HK": 1}))
        with self.assertRaises(ValueError):
            calib_pool.eval_formula("__import__('os').system('echo hi')", {"HK": 1})


class TestRankCheck(unittest.TestCase):
    def rows(self, n=30, noise_old=3.0, noise_new=0.3, seed=1, form="single"):
        rng = random.Random(seed)
        out = []
        for i in range(n):
            y = rng.lognormvariate(0, 1)
            out.append({"file": f"f{i}", "form": form, "y": y, "w": 1.0,
                        "new": y + rng.gauss(0, noise_new), "old": y + rng.gauss(0, noise_old)})
        return out

    def test_spearman_basics(self):
        self.assertAlmostEqual(rank_check.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(rank_check.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertEqual(rank_check.ranks([5, 1, 5, 2]), [3.5, 1.0, 3.5, 2.0])

    def test_clear_improvement_passes(self):
        res = rank_check.check(self.rows(), iters=300)
        self.assertEqual(res["verdict"], "PASS", res)

    def test_no_improvement_fails(self):
        rows = self.rows(noise_old=0.3, noise_new=0.3)
        for r in rows:
            r["new"] = r["old"]
        res = rank_check.check(rows, iters=300)
        self.assertEqual(res["verdict"], "FAIL")
        self.assertFalse(res["criteria"]["gain"])

    def test_form_regression_blocks(self):
        good = self.rows(n=30, seed=2, form="single")
        bad = self.rows(n=8, noise_old=0.1, noise_new=0.1, seed=3, form="thread")
        for r in bad:
            r["new"] = -r["y"]          # new formula inverts the thread ranking
        res = rank_check.check(good + bad, iters=300)
        self.assertFalse(res["forms"]["thread"]["ok"])
        self.assertEqual(res["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
