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
