"""Tests for the optional x-api fetcher. A fake opener stands in for the network.

Run:  python -m unittest test_xapi.py   (from this directory)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xapi  # noqa: E402

HEAD = {
    "data": {"id": "1001", "text": "我用 AI 写作半年后删掉的 7 个提示词", "author_id": "u1", "conversation_id": "1001",
             "created_at": "2026-11-10T13:00:00.000Z", "lang": "zh",
             "public_metrics": {"retweet_count": 9, "reply_count": 17, "like_count": 54, "quote_count": 3,
                                "bookmark_count": 31, "impression_count": 2130},
             "attachments": {"media_keys": ["3_1"]},
             "entities": {"urls": [{"expanded_url": "https://example.com/x"}]}},
    "includes": {"users": [{"id": "u1", "username": "me"}], "media": [{"media_key": "3_1", "type": "photo"}]},
}
REPLIES = {
    "data": [
        {"id": "2001", "text": "还可以加一个", "author_id": "u2", "conversation_id": "1001",
         "referenced_tweets": [{"type": "replied_to", "id": "1001"}], "in_reply_to_user_id": "u1",
         "public_metrics": {"like_count": 12, "retweet_count": 0, "reply_count": 0, "quote_count": 0}},
        {"id": "2002", "text": "求模板", "author_id": "u3", "conversation_id": "1001",
         "referenced_tweets": [{"type": "replied_to", "id": "1001"}], "in_reply_to_user_id": "u1",
         "public_metrics": {"like_count": 40, "retweet_count": 0, "reply_count": 0, "quote_count": 0}},
    ],
    "includes": {"users": [{"id": "u1", "username": "me"}, {"id": "u2", "username": "alice"},
                           {"id": "u3", "username": "bob"}]},
}


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeOpener:
    def __init__(self, routes: dict[str, dict] | None = None, error: int | None = None):
        self.routes = routes or {}
        self.error = error
        self.calls: list[str] = []

    def __call__(self, req):
        self.calls.append(req.full_url)
        assert req.headers.get("Authorization", "").startswith("Bearer "), "missing bearer"
        if self.error:
            raise urllib.error.HTTPError(req.full_url, self.error, "err", {"x-rate-limit-reset": "1762952580"}, io.BytesIO(b"{}"))
        path = urllib.parse.urlparse(req.full_url).path.replace("/2", "", 1)
        for prefix, body in self.routes.items():
            if path.startswith(prefix):
                return FakeResp(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected call {path}")


def run(argv, opener):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = xapi.main(argv, opener=opener)
    return code, out.getvalue(), err.getvalue()


class TestMapping(unittest.TestCase):
    def test_record_from_api(self):
        r = xapi.records_from_response(HEAD, datetime(2026, 11, 12, tzinfo=timezone.utc))[0]
        self.assertEqual(r["author"], "me")
        self.assertEqual(r["impressions"], 2130)
        self.assertEqual(r["bookmarks"], 31)
        self.assertEqual(r["media"], "photo")
        self.assertTrue(r["has_link"])
        self.assertEqual(r["url"], "https://x.com/me/status/1001")

    def test_non_public_metrics_win(self):
        t = dict(HEAD["data"], non_public_metrics={"impression_count": 2200, "user_profile_clicks": 38,
                                                    "url_link_clicks": 4, "engagements": 120})
        r = xapi.record_from_api(t, HEAD["includes"], datetime.now(timezone.utc))
        self.assertEqual(r["impressions"], 2200)
        self.assertEqual(r["profile_visits"], 38)
        self.assertEqual(r["link_clicks"], 4)

    def test_reply_mapping(self):
        rs = xapi.records_from_response(REPLIES, datetime.now(timezone.utc))
        self.assertEqual(rs[0]["in_reply_to_id"], "1001")
        self.assertEqual(rs[0]["in_reply_to_user"], "me")


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        (self.proj / ".cheatx-secrets.json").write_text(json.dumps({"x_bearer_token": "test-token"}), encoding="utf-8")
        os.environ.pop("X_BEARER_TOKEN", None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_sends_nothing(self):
        opener = FakeOpener()
        code, out, err = run(["post", "1001", "--out", str(self.proj / "p"), "--project", str(self.proj)], opener)
        self.assertEqual(code, 5)
        self.assertEqual(opener.calls, [])
        self.assertIn("预估上限", err)
        self.assertIn("--yes", err)

    def test_post_yes_writes_report_via_importer(self):
        opener = FakeOpener({"/tweets/search/recent": REPLIES, "/tweets/1001": HEAD})
        out_dir = self.proj / "posts" / "p"
        code, out, err = run(["post", "https://x.com/me/status/1001", "--out", str(out_dir), "--project",
                              str(self.proj), "--replies", "20", "--yes"], opener)
        self.assertEqual(code, 0, err)
        summary = json.loads(out)
        self.assertEqual(summary["metrics"]["impressions"], 2130)
        self.assertEqual(summary["replies_captured"], 2)
        md = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("x-api", md)
        self.assertLess(md.index("求模板"), md.index("还可以加一个"))
        self.assertTrue(any((self.proj / ".cheatx-cache" / "x-api").glob("post-1001-*.csv")))
        self.assertEqual(len(opener.calls), 2)

    def test_text_requests_no_metrics(self):
        opener = FakeOpener({"/tweets/1001": HEAD})
        code, out, err = run(["text", "1001", "--project", str(self.proj), "--yes"], opener)
        self.assertEqual(code, 0, err)
        self.assertNotIn("public_metrics", urllib.parse.unquote(opener.calls[0]))
        self.assertEqual(json.loads(out)["text"], HEAD["data"]["text"])

    def test_rate_limit(self):
        code, out, err = run(["text", "1001", "--project", str(self.proj), "--yes"], FakeOpener(error=429))
        self.assertEqual(code, 4)
        self.assertIn("429", err)

    def test_missing_token(self):
        (self.proj / ".cheatx-secrets.json").unlink()
        with self.assertRaises(SystemExit) as cm:
            run(["text", "1001", "--project", str(self.proj), "--yes"], FakeOpener())
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
