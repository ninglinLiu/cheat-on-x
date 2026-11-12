"""Unit tests for x-csv-import. Synthetic data only, no network.

Run:  python -m unittest test_xcsv.py   (from this directory)
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import import_csv  # noqa: E402
from aliases import map_columns  # noqa: E402
from xcsv import (  # noqa: E402
    derive_form, derived_metrics, extract_status_id, load_posts, merge_records, parse_number,
    parse_time, weighted_length,
)

UTC = timezone.utc

USERSCRIPT_HEADER = ["post_id", "url", "author", "created_at", "captured_at", "form", "text",
                     "impressions", "likes", "reposts", "quotes", "replies", "bookmarks",
                     "engagements", "profile_visits", "new_follows", "link_clicks", "detail_expands",
                     "media_views", "shares", "has_link", "media", "lang", "in_reply_to_id",
                     "in_reply_to_user", "conversation_id", "quoted_id", "is_note_tweet", "is_article",
                     "source"]


def write_csv(path: Path, header: list[str], rows: list[dict], bom: bool = False) -> Path:
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})
    return path


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = import_csv.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        cases = {"1,234": 1234, "1.2K": 1200, "1.2k": 1200, "3.4M": 3400000, "1.2万": 12000,
                 "3亿": 300000000, "12": 12, " 7 ": 7, "": None, "-": None, "—": None,
                 "N/A": None, "1 234": 1234, "2.5w": 25000, "abc": None}
        for s, want in cases.items():
            self.assertEqual(parse_number(s), want, s)

    def test_times(self):
        self.assertEqual(parse_time("2026-11-12T13:03:00Z"), datetime(2026, 11, 12, 13, 3, tzinfo=UTC))
        legacy = parse_time("Wed Nov 12 13:03:00 +0000 2026")
        self.assertEqual(legacy, datetime(2026, 11, 12, 13, 3, tzinfo=UTC))
        cst = timezone(timedelta(hours=8))
        self.assertEqual(parse_time("2026-11-12 21:03", cst), datetime(2026, 11, 12, 21, 3, tzinfo=cst))
        self.assertIsNotNone(parse_time("Nov 12, 2026"))
        self.assertEqual(parse_time("1762952580"), datetime.fromtimestamp(1762952580, tz=UTC))
        self.assertIsNone(parse_time(""))

    def test_status_ids(self):
        self.assertEqual(extract_status_id("https://x.com/abc/status/1988765432109876543?s=20"), "1988765432109876543")
        self.assertEqual(extract_status_id("https://twitter.com/abc/status/123456789"), "123456789")
        self.assertEqual(extract_status_id("https://x.com/i/web/status/1988765432109876543"), "1988765432109876543")
        self.assertEqual(extract_status_id("1988765432109876543"), "1988765432109876543")
        self.assertEqual(extract_status_id("1.988e18"), None)
        self.assertIsNone(extract_status_id("hello"))

    def test_weighted_length(self):
        self.assertEqual(weighted_length("abc"), 3)
        self.assertEqual(weighted_length("中文"), 4)


class TestContract(unittest.TestCase):
    def test_userscript_header_matches_canonical(self):
        import re
        from xcsv import CANONICAL_CSV_HEADER
        js = Path(HERE, "..", "..", "..", "userscripts", "cheatx-exporter.user.js").read_text(encoding="utf-8")
        block = re.search(r"const HEADER = \[(.*?)\];", js, re.S).group(1)
        self.assertEqual(re.findall(r"'([a-z_]+)'", block), CANONICAL_CSV_HEADER)
        self.assertEqual(USERSCRIPT_HEADER, CANONICAL_CSV_HEADER)


class TestMapping(unittest.TestCase):
    def test_analytics_style_headers(self):
        headers = ["Post id", "Date", "Post text", "Post Link", "Impressions", "Likes", "Engagements",
                   "Bookmarks", "Shares", "New follows", "Replies", "Reposts", "Profile visits",
                   "Detail Expands", "URL Clicks", "Hashtag Clicks"]
        mapping, unmapped = map_columns(headers)
        self.assertEqual(mapping["Post id"], "post_id")
        self.assertEqual(mapping["Impressions"], "impressions")
        self.assertEqual(mapping["New follows"], "new_follows")
        self.assertEqual(mapping["URL Clicks"], "link_clicks")
        self.assertEqual(unmapped, ["Hashtag Clicks"])

    def test_chinese_headers(self):
        mapping, _ = map_columns(["帖子链接", "发布时间", "正文", "展示次数", "喜欢", "转帖", "回复", "书签", "个人资料访问"])
        self.assertEqual(set(mapping.values()),
                         {"url", "created_at", "text", "impressions", "likes", "reposts", "replies",
                          "bookmarks", "profile_visits"})

    def test_override_wins(self):
        mapping, _ = map_columns(["Views", "Impressions"], {"Views": "impressions"})
        self.assertEqual(mapping["Views"], "impressions")
        self.assertNotIn("Impressions", mapping)

    def test_bad_override(self):
        with self.assertRaises(ValueError):
            map_columns(["Views"], {"Views": "not_a_field"})


class FixtureMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def userscript_rows(self, captured: str, imp: int) -> list[dict]:
        return [
            {"post_id": "1001", "author": "me", "created_at": "2026-11-10T13:00:00Z", "captured_at": captured,
             "text": "我用 AI 写作半年后删掉的 7 个提示词", "impressions": str(imp), "likes": "54", "reposts": "9",
             "quotes": "3", "replies": "17", "bookmarks": "31", "has_link": "false", "media": "image"},
            {"post_id": "1002", "author": "me", "created_at": "2026-11-10T13:01:00Z", "captured_at": captured,
             "text": "2/ 第一个……", "in_reply_to_id": "1001", "in_reply_to_user": "me",
             "conversation_id": "1001", "impressions": "300"},
            {"post_id": "2001", "author": "alice", "created_at": "2026-11-10T14:00:00Z", "captured_at": captured,
             "text": "还可以加一个：让它先列反例", "in_reply_to_id": "1001", "in_reply_to_user": "me",
             "conversation_id": "1001", "likes": "12"},
            {"post_id": "2002", "author": "bob", "created_at": "2026-11-10T15:00:00Z", "captured_at": captured,
             "text": "求模板", "in_reply_to_id": "1001", "in_reply_to_user": "me", "conversation_id": "1001",
             "likes": "40"},
            {"post_id": "3001", "author": "carol", "created_at": "2026-11-10T16:00:00Z", "captured_at": captured,
             "text": "这个清单值得收藏", "quoted_id": "1001", "likes": "5"},
            {"post_id": "1003", "author": "me", "created_at": "2026-11-12T12:00:00Z", "captured_at": captured,
             "text": "今天刚发的一条", "impressions": "999999", "likes": "1"},
        ]


class TestLoadMerge(FixtureMixin, unittest.TestCase):
    def test_merge_newer_wins_and_fills_gaps(self):
        old = write_csv(self.dir / "a.csv", USERSCRIPT_HEADER, [
            {"post_id": "1001", "author": "me", "captured_at": "2026-11-11T00:00:00Z", "impressions": "800",
             "profile_visits": "38"}])
        new = write_csv(self.dir / "b.csv", USERSCRIPT_HEADER, [
            {"post_id": "1001", "author": "me", "captured_at": "2026-11-12T13:00:00Z", "impressions": "2,130"}],
            bom=True)
        recs = []
        for p in (new, old):
            recs.extend(load_posts(p)[0])
        m = merge_records(recs)["1001"]
        self.assertEqual(m["impressions"], 2130)
        self.assertEqual(m["profile_visits"], 38)
        self.assertEqual(len(m["_files"]), 2)

    def test_forms(self):
        p = write_csv(self.dir / "x.csv", USERSCRIPT_HEADER, self.userscript_rows("2026-11-12T13:00:00Z", 2130) + [
            {"post_id": "4001", "author": "me", "text": "长" * 200},
            {"post_id": "4002", "author": "me", "text": "x", "is_article": "true"},
            {"post_id": "4003", "author": "me", "text": "short"},
        ])
        merged = merge_records(load_posts(p)[0])
        self.assertEqual(derive_form(merged["1001"], merged), "thread")
        self.assertEqual(derive_form(merged["1002"], merged), "thread")
        self.assertEqual(derive_form(merged["2001"], merged), "reply")
        self.assertEqual(derive_form(merged["3001"], merged), "quote")
        self.assertEqual(derive_form(merged["4001"], merged), "long")
        self.assertEqual(derive_form(merged["4002"], merged), "article")
        self.assertEqual(derive_form(merged["4003"], merged), "single")

    def test_derived(self):
        d = derived_metrics({"impressions": 2000, "likes": 50, "reposts": 10, "quotes": 2, "replies": 18,
                             "bookmarks": 20, "new_follows": 6})
        self.assertAlmostEqual(d["interaction_rate"], 0.05)
        self.assertAlmostEqual(d["bookmark_like_ratio"], 0.4)
        self.assertAlmostEqual(d["repost_quote_rate"], 0.006)
        self.assertAlmostEqual(d["follows_per_1k"], 3.0)
        self.assertIsNone(d["profile_visit_rate"])


class TestCLI(FixtureMixin, unittest.TestCase):
    def make_project(self) -> Path:
        proj = self.dir / "proj"
        (proj / "predictions").mkdir(parents=True)
        (proj / "posts" / "2026-11-10_aaa_清单").mkdir(parents=True)
        (proj / "posts" / "2026-11-10_aaa_清单" / "final.md").write_text("定稿正文", encoding="utf-8")
        (proj / "predictions" / "2026-11-10_aaa_清单.md").write_text(
            "# 清单 — 预测日志\n\n**Form**: thread (7)\n**Published at**: 2026-11-10T21:00+08:00\n"
            "**Status ID**: 1001\n**Post Folder**: posts/2026-11-10_aaa_清单/\n\n## 预测 v1\n\nx\n\n## 复盘\n",
            encoding="utf-8")
        (proj / "predictions" / "2026-11-12_bbb_今天.md").write_text(
            "# 今天 — 预测日志\n\n**Form**: single\n**Status ID**: 1003\n\n## 预测 v1\n\nx\n", encoding="utf-8")
        state = {"schema_version": "x1.0", "edition": "x", "x_handle": "@me",
                 "retro_window_hours": 48, "retro_window_hours_longform": 168,
                 "pending_retros": [
                     {"file": "predictions/2026-11-10_aaa_清单.md", "status_id": "1001", "form": "thread",
                      "published_at": "2026-11-10T21:00:00+08:00", "due_at": "2026-11-12T21:00:00+08:00"},
                     {"file": "predictions/2026-11-12_bbb_今天.md", "status_id": "1003", "form": "single",
                      "published_at": "2026-11-12T20:00:00+08:00", "due_at": "2026-11-14T20:00:00+08:00"},
                 ]}
        (proj / ".cheatx-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return proj

    def test_post_report(self):
        csvp = write_csv(self.dir / "x.csv", USERSCRIPT_HEADER, self.userscript_rows("2026-11-12T13:30:00Z", 2130))
        out = self.dir / "post"
        code, stdout, _ = run_cli(["post", str(csvp), "--id", "https://x.com/me/status/1001", "--out", str(out),
                                   "--window-hours", "48"])
        self.assertEqual(code, 0)
        summary = json.loads(stdout)
        self.assertEqual(summary["metrics"]["impressions"], 2130)
        self.assertEqual(summary["replies_captured"], 2)
        self.assertEqual(summary["quotes_captured"], 1)
        md = (out / "report.md").read_text(encoding="utf-8")
        self.assertIn("| 曝光 | 2,130 |", md)
        self.assertIn("互动率", md)
        self.assertLess(md.index("求模板"), md.index("还可以加一个"))   # sorted by likes
        self.assertNotIn("alice", md)                                     # handles omitted
        self.assertNotIn("bob", md)
        self.assertIn("这个清单值得收藏", md)
        self.assertNotIn(str(self.dir), md)                               # no absolute paths

    def test_text_has_no_metrics(self):
        csvp = write_csv(self.dir / "x.csv", USERSCRIPT_HEADER, self.userscript_rows("2026-11-12T13:30:00Z", 2130))
        code, stdout, _ = run_cli(["text", str(csvp), "--id", "1001"])
        self.assertEqual(code, 0)
        obj = json.loads(stdout)
        self.assertEqual(set(obj), {"post_id", "found", "author", "created_at", "text"})
        self.assertNotIn("2130", stdout)

    def test_due_only_processes_due_posts(self):
        proj = self.make_project()
        csvp = write_csv(self.dir / "x.csv", USERSCRIPT_HEADER, self.userscript_rows("2026-11-12T13:30:00Z", 2130))
        code, stdout, _ = run_cli(["due", str(csvp), "--project", str(proj), "--now", "2026-11-12T22:00:00+08:00"])
        self.assertEqual(code, 0)
        res = json.loads(stdout)
        self.assertEqual(res["not_yet_due"], 1)
        self.assertEqual(len(res["processed"]), 1)
        self.assertEqual(res["processed"][0]["status_id"] if "status_id" in res["processed"][0]
                         else res["processed"][0]["post_id"], "1001")
        self.assertNotIn("999999", stdout)                 # the not-yet-due post stays blind
        report = proj / "posts" / "2026-11-10_aaa_清单" / "report.md"
        self.assertTrue(report.is_file())
        self.assertIn("定稿正文", report.read_text(encoding="utf-8"))

    def test_history_skips_pending_and_tiers(self):
        proj = self.make_project()
        rows = [{"post_id": str(5000 + i), "author": "me", "created_at": f"2026-10-{10 + i:02d}T12:00:00Z",
                 "text": f"post {i}", "impressions": str(v)} for i, v in enumerate([100, 400, 500, 600, 2000])]
        rows += self.userscript_rows("2026-11-12T13:30:00Z", 2130)
        csvp = write_csv(self.dir / "h.csv", USERSCRIPT_HEADER, rows)
        code, stdout, _ = run_cli(["history", str(csvp), "--handle", "@me", "--project", str(proj),
                                   "--samples-dir", str(self.dir / "samples")])
        self.assertEqual(code, 0)
        res = json.loads(stdout)
        ids = {p["post_id"] for p in res["posts"]}
        self.assertNotIn("1001", ids)          # pending retro → skipped
        self.assertNotIn("1003", ids)
        self.assertNotIn("1002", ids)          # thread continuation dropped
        self.assertNotIn("999999", stdout)
        self.assertEqual(res["skipped_pending_retro"], 2)
        self.assertEqual(res["median_impressions"], 500)
        tiers = {p["post_id"]: p["tier"] for p in res["posts"]}
        self.assertEqual(tiers["5004"], "高")
        self.assertEqual(tiers["5000"], "低")
        self.assertTrue((self.dir / "samples" / "5004.md").is_file())

    def test_inspect_and_map(self):
        csvp = write_csv(self.dir / "third.csv", ["Tweet ID", "Views", "Faves", "Text"],
                         [{"Tweet ID": "777", "Views": "1.2K", "Faves": "30", "Text": "hi"}])
        code, stdout, _ = run_cli(["inspect", str(csvp)])
        self.assertEqual(code, 0)
        self.assertIn("'Faves'", stdout)
        self.assertNotIn("1.2K", stdout)
        out = self.dir / "p"
        code, stdout, _ = run_cli(["--map", "Faves=likes", "post", str(csvp), "--id", "777", "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["metrics"]["likes"], 30)
        self.assertEqual(json.loads(stdout)["metrics"]["impressions"], 1200)

    def test_trends(self):
        p = write_csv(self.dir / "t.csv", ["name", "meta", "domain", "captured_at"],
                      [{"name": "OpenModel", "meta": "12.3K posts", "domain": "Technology",
                        "captured_at": "2026-11-12T02:00:00Z"}])
        code, stdout, _ = run_cli(["trends", str(p)])
        self.assertEqual(code, 0)
        item = json.loads(stdout.strip().splitlines()[0])
        self.assertEqual(item["source"], "trend:x-trends")
        self.assertEqual(len(item["id"]), 12)
        self.assertTrue(item["expires_at"].startswith("2026-11-13T02:00"))


if __name__ == "__main__":
    unittest.main()
