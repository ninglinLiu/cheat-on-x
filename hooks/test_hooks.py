"""Tests for the cheat-on-x hooks. Runs the real bash scripts against a temp project.

Run:  python -m unittest test_hooks.py   (from hooks/)
Set CHEATX_BASH to a bash binary if `bash` on PATH is not a real bash (e.g. WSL launcher on Windows).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_bash() -> str | None:
    if os.environ.get("CHEATX_BASH"):
        return os.environ["CHEATX_BASH"]
    for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.isfile(p):
            return p
    b = shutil.which("bash")
    if b and "system32" not in b.lower():
        return b
    return None


BASH = find_bash()

PRED = """# 清单 — 预测日志

**Post ID**: abc
**Form**: thread (7)

---

## 输入快照

**分数 (v0)**: HK4 / RP3 → composite=**7.60**

## 预测 v1

**Bucket**: `命中`
**中枢**: 800

## 推理因素

| SV=5 | 强 + |

## 预测 v2（replaces v1）

**中枢**: 900

## 复盘

（待填——复盘窗口到期后跑 `/cheatx-retro`）
"""


@unittest.skipIf(BASH is None, "no usable bash found")
class TestImmutability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        (self.proj / "predictions").mkdir()
        self.pred = self.proj / "predictions" / "2026-11-12_abc_清单.md"
        self.pred.write_text(PRED, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload: dict, env_extra: dict | None = None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.proj), **(env_extra or {}))
        p = subprocess.run([BASH, str(HERE / "prediction-immutability.sh")], input=json.dumps(payload).encode("utf-8"),
                           capture_output=True, env=env, timeout=60)
        return p.returncode, p.stderr.decode("utf-8", "replace")

    def edit(self, old, new="X", path=None, tool="Edit"):
        return {"tool_name": tool, "tool_input": {"file_path": str(path or self.pred), "old_string": old, "new_string": new}}

    def test_edit_prediction_blocked_with_exit_2(self):
        code, err = self.run_hook(self.edit("**中枢**: 800"))
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", err)

    def test_edit_v2_and_reasoning_blocked(self):
        self.assertEqual(self.run_hook(self.edit("**中枢**: 900"))[0], 2)
        self.assertEqual(self.run_hook(self.edit("| SV=5 | 强 + |"))[0], 2)

    def test_header_edit_allowed(self):
        self.assertEqual(self.run_hook(self.edit("**Form**: thread (7)"))[0], 0)

    def test_retro_append_with_blank_lines_allowed(self):
        old = "## 复盘\n\n（待填——复盘窗口到期后跑 `/cheatx-retro`）\n"
        self.assertEqual(self.run_hook(self.edit(old))[0], 0)

    def test_edit_spanning_into_prediction_blocked(self):
        old = "**中枢**: 900\n\n## 复盘"
        self.assertEqual(self.run_hook(self.edit(old))[0], 2)

    def test_input_snapshot_is_locked(self):
        # the recorded scores are part of the prediction (upstream left them editable)
        self.assertEqual(self.run_hook(self.edit("**分数 (v0)**: HK4 / RP3"))[0], 2)

    def test_v2_insert_before_retro_allowed(self):
        old = "## 复盘\n"
        new = "## 预测 v2（replaces v1）\n\n**中枢**: 950\n\n## 复盘\n"
        self.assertEqual(self.run_hook(self.edit(old, new))[0], 0)

    def test_append_after_retro_allowed(self):
        self.assertEqual(self.run_hook(self.edit("（待填——复盘窗口到期后跑 `/cheatx-retro`）"))[0], 0)

    def test_non_prediction_file_in_predictions_dir_allowed(self):
        other = self.proj / "predictions" / "README.md"
        other.write_text("# notes\n\n## 说明\n\nfoo\n", encoding="utf-8")
        self.assertEqual(self.run_hook(self.edit("foo", path=other))[0], 0)

    def test_write_existing_blocked_new_allowed(self):
        w = {"tool_name": "Write", "tool_input": {"file_path": str(self.pred), "content": "x"}}
        self.assertEqual(self.run_hook(w)[0], 2)
        new = {"tool_name": "Write", "tool_input": {"file_path": str(self.proj / "predictions" / "new.md"), "content": "x"}}
        self.assertEqual(self.run_hook(new)[0], 0)

    def test_outside_predictions_allowed(self):
        other = self.proj / "drafts.md"
        other.write_text(PRED, encoding="utf-8")
        self.assertEqual(self.run_hook(self.edit("**中枢**: 800", path=other))[0], 0)

    def test_multiedit_blocked(self):
        p = {"tool_name": "MultiEdit", "tool_input": {"file_path": str(self.pred), "edits": [
            {"old_string": "**Form**: thread (7)", "new_string": "a"},
            {"old_string": "**Bucket**: `命中`", "new_string": "b"}]}}
        self.assertEqual(self.run_hook(p)[0], 2)

    def test_windows_backslash_path(self):
        p = self.edit("**中枢**: 800", path=str(self.pred).replace("/", "\\"))
        self.assertEqual(self.run_hook(p)[0], 2)

    def test_bypass(self):
        self.assertEqual(self.run_hook(self.edit("**中枢**: 800"), {"CHEATX_BYPASS_IMMUTABILITY": "1"})[0], 0)


class TestSessionStart(unittest.TestCase):
    def test_report(self):
        import sys
        sys.path.insert(0, str(HERE))
        import session_start  # noqa: E402
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            now = datetime.now(timezone.utc).astimezone()
            state = {
                "schema_version": "x1.0", "edition": "x", "rubric_version": "v0", "calibration_samples": 6,
                "target_posts_per_day": 3, "hooks_installed": True,
                "pending_retros": [
                    {"file": "predictions/a.md", "due_at": (now - timedelta(hours=1)).isoformat()},
                    {"file": "predictions/b.md", "due_at": (now + timedelta(hours=5)).isoformat()},
                ],
                "recent_publishes": [{"at": (now - timedelta(minutes=30)).isoformat(), "form": "single"},
                                     {"at": (now - timedelta(minutes=10)).isoformat(), "form": "reply"}],
                "queue": [],
            }
            (proj / ".cheatx-state.json").write_text(json.dumps(state), encoding="utf-8")
            (proj / "candidates.md").write_text(
                "### [tier1] 删掉的提示词\n- **composite (v0)**: 7.6\n### [skip] 跳过的候选ZZ\n"
                "### [tier2] 过期热点\n- **expires_at**: 2000-01-01T00:00:00+00:00\n", encoding="utf-8")
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                session_start.main(["x", str(proj)])
            out = buf.getvalue()
            self.assertIn("到期待复盘 1 条", out)
            self.assertIn("24 小时内还有 1 条", out)
            self.assertIn("今天主帖 1 / 3", out)
            self.assertIn("回复 1", out)
            self.assertIn("🔴", out)
            self.assertIn("删掉的提示词", out)
            self.assertNotIn("过期热点", out)
            self.assertNotIn("跳过的候选ZZ", out)
            self.assertIn("🟡", out)

    def test_bump_hint_and_deferred_setup(self):
        import sys
        sys.path.insert(0, str(HERE))
        import session_start  # noqa: E402
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            state = {"schema_version": "x1.0", "edition": "x", "calibration_samples": 12,
                     "calibration_samples_at_last_bump": 5, "hooks_installed": True,
                     "benchmark_status": "pending", "deferred_setup": ["history", "benchmark"]}
            (proj / ".cheatx-state.json").write_text(json.dumps(state), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                session_start.main(["x", str(proj)])
            out = buf.getvalue()
            self.assertIn("已有 7 条新复盘", out)
            self.assertIn("推迟的设置：history / benchmark", out)
            self.assertNotIn("还没导入对标账号", out)     # deferred → no nagging warning
            self.assertIn("托管模式", out)

    def test_silent_outside_project(self):
        import sys
        sys.path.insert(0, str(HERE))
        import session_start  # noqa: E402
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                session_start.main(["x", d])
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
