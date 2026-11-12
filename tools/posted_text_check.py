#!/usr/bin/env python3
"""posted_text_check.py — did the text you posted match the text you predicted?

Compares posts/<id>/final.md (or the draft) with the text that actually went out on X, after
removing things that are not post content:
  - YAML frontmatter (form / media / has_link …)
  - the "## 被引用 / 被回复的帖子" context section and anything after it
  - thread numbering like "1/", "2/7", "(3/7)", "3." at the start of a part
  - t.co / short links and trailing whitespace

Usage:
  python tools/posted_text_check.py posts/<id>/final.md posted.txt
  python tools/posted_text_check.py posts/<id>/final.md --text "the posted text"
Output: integer 0-100 (normalized char-level difference) and a verdict on stderr:
  < 10 same · 10-29 diff · >= 30 diff ⚠️ (integrity warning)
Exit: 0 ok · 2 bad args · 3 read error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diff_pct import diff_pct  # noqa: E402

_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
_CONTEXT = re.compile(r"^##\s*被引用.*\Z|^##\s*被回复.*\Z", re.S | re.M)
_NUMBERING = re.compile(r"^[ \t]*(?:\(?\d{1,2}[ \t]*/[ \t]*\d{0,2}\)?|\d{1,2}[.、])[ \t]*", re.M)
_LINKS = re.compile(r"https?://t\.co/\S+|https?://\S+")


def clean(text: str) -> str:
    text = _FRONTMATTER.sub("", text)
    text = _CONTEXT.sub("", text)
    text = _LINKS.sub("", text)
    text = _NUMBERING.sub("", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def verdict(pct: int) -> str:
    if pct < 10:
        return "same"
    if pct < 30:
        return f"diff {pct}%"
    return f"diff {pct}% ⚠️"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("final")
    p.add_argument("posted", nargs="?")
    p.add_argument("--text")
    a = p.parse_args(argv)
    if bool(a.posted) == bool(a.text):
        print("给一个 posted 文件，或用 --text 直接传正文（二选一）", file=sys.stderr)
        return 2
    try:
        final = Path(a.final).read_text(encoding="utf-8")
        posted = a.text if a.text is not None else Path(a.posted).read_text(encoding="utf-8")
    except OSError as e:
        print(f"read error: {e}", file=sys.stderr)
        return 3
    pct, _backend = diff_pct(clean(final), clean(posted))
    print(pct)
    print(f"Posted Text Check: {verdict(pct)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
