#!/usr/bin/env python3
"""leak_check.py — blind-channel leak guard for rubric_notes.md (cheat-on-x).

rubric_notes.md is the ONLY rules file the blind scoring sub-agent may read. If it contains a real
post's outcome (a link, a status id, an impression count, a reply quote, a handle), the "blind"
score is contaminated. Run this after every write to rubric_notes.md; a non-zero exit means
abort and roll back that write.

Usage:  python tools/leak_check.py rubric_notes.md [more files...]
Exit:   0 clean · 1 leak signals found · 2 file problem

The patterns below are the single source of truth. cheatx-score-blind uses GREP_PATTERN (a
ripgrep-compatible subset without the @handle rule) for its own read-time self-check.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LEAK_PATTERNS: list[tuple[str, str]] = [
    ("帖子链接", r"(?:x|twitter)\.com/[^\s/]+/status/\d+"),
    ("status id", r"status/\d{8,}|(?<!\d)\d{15,20}(?!\d)"),
    ("数字 + 曝光类指标", r"\d[\d,.]*\s*[kKmMwW万千]?\s*次?(?:曝光|浏览|阅读|impressions?|views?)"),
    ("指标 + 数字", r"(?:曝光|浏览量|impressions?|views?)\s*[:：=]\s*\d"),
    ("实绩字样", r"实绩|实际曝光|实际浏览"),
    ("@handle", r"(?<![\w.@])@[A-Za-z0-9_]{3,15}\b"),
]

GREP_PATTERN = (r"(x|twitter)\.com/[^ /]+/status/[0-9]+|status/[0-9]{8,}|[0-9]{15,20}"
                r"|[0-9][0-9,.]*\s*[kKmMwW万千]?\s*次?(曝光|浏览|阅读|impressions?|views?)"
                r"|(曝光|浏览量|impressions?|views?)\s*[:：=]\s*[0-9]|实绩|实际曝光|实际浏览")

_COMPILED = [(name, re.compile(p, re.IGNORECASE)) for name, p in LEAK_PATTERNS]


def scan(text: str) -> list[tuple[int, str, str]]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, rx in _COMPILED:
            m = rx.search(line)
            if m:
                hits.append((lineno, name, line.strip()))
                break
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    total = 0
    for f in argv:
        p = Path(f)
        if not p.is_file():
            print(f"❌ 找不到文件：{f}", file=sys.stderr)
            return 2
        hits = scan(p.read_text(encoding="utf-8"))
        for lineno, name, line in hits:
            print(f"{f}:{lineno}: [{name}] {line[:160]}")
        total += len(hits)
    if total:
        print(f"\n⚠️ 发现 {total} 处疑似实际数据。rubric_notes.md 只能放通用规则——把这些内容移到 rubric-memo.md，"
              "或抽象成不带样本名 / 数字的说法。")
        return 1
    print("✅ 未发现泄漏信号")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
