"""Core parsing for cheat-on-x CSV imports (stdlib only).

Turns any supported CSV export into canonical post records:
  - the cheatx userscript export (canonical column names)
  - X Analytics content export (Premium)
  - third-party userscripts / extensions (via aliases.py or --map)
"""
from __future__ import annotations

import csv
import io
import os
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from aliases import METRIC_FIELDS, map_columns, norm_key

Record = dict[str, Any]

# Column order of the canonical CSV. The userscript (userscripts/cheatx-exporter.user.js, HEADER)
# and the x-api fetcher write exactly these columns; test_xcsv.py checks they stay in sync.
CANONICAL_CSV_HEADER = [
    "post_id", "url", "author", "created_at", "captured_at", "form", "text",
    "impressions", "likes", "reposts", "quotes", "replies", "bookmarks",
    "engagements", "profile_visits", "new_follows", "link_clicks", "detail_expands",
    "media_views", "shares", "has_link", "media", "lang", "in_reply_to_id",
    "in_reply_to_user", "conversation_id", "quoted_id", "is_note_tweet", "is_article", "source",
]
TREND_CSV_HEADER = ["name", "meta", "domain", "url", "captured_at"]


def write_canonical_csv(path: str | Path, rows: Iterable[dict], header: list[str] | None = None) -> Path:
    header = header or CANONICAL_CSV_HEADER
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else (str(r[k]).lower() if isinstance(r.get(k), bool)
                                                       else r[k])) for k in header})
    return path

# ---------------------------------------------------------------- numbers

_MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "w": 1e4, "万": 1e4, "千": 1e3, "亿": 1e8}
_NUM_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([kmbw万千亿]?)$", re.IGNORECASE)
_EMPTY = {"", "-", "—", "–", "n/a", "na", "none", "null", "nan", "--"}


def parse_number(value: Any) -> int | float | None:
    """'1,234' → 1234 · '1.2K' → 1200 · '1.2万' → 12000 · '3.4M' → 3400000 · '' / '-' → None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if s.lower() in _EMPTY:
        return None
    s = s.replace(",", "").replace("，", "").replace(" ", "")
    m = _NUM_RE.match(s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit:
        num *= _MULT[unit]
    return int(round(num)) if abs(num - round(num)) < 1e-9 else num


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "是"}:
        return True
    if s in {"0", "false", "no", "n", "否"}:
        return False
    return None


# ---------------------------------------------------------------- time

_TIME_FORMATS = [
    "%a %b %d %H:%M:%S %z %Y",      # Twitter legacy: Wed Oct 10 20:19:24 +0000 2018
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%a, %b %d, %Y",                # Wed, Nov 12, 2026
    "%b %d, %Y",                    # Nov 12, 2026
    "%d %b %Y",
]


def parse_time(value: Any, default_tz: timezone | None = None) -> datetime | None:
    """Parse common export timestamps. Naive values get `default_tz` (local time if None)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in _EMPTY:
        return None
    dt = None
    iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        for fmt in _TIME_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        if s.isdigit() and len(s) in (10, 13):  # epoch seconds / millis
            ts = int(s) / (1000 if len(s) == 13 else 1)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz) if default_tz else dt.astimezone()
    return dt


# ---------------------------------------------------------------- ids

_STATUS_RE = re.compile(r"(?:x|twitter)\.com/(?:[^/\s]+|i/web)/status(?:es)?/(\d{1,25})", re.IGNORECASE)
_HANDLE_FROM_URL_RE = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status", re.IGNORECASE)


def extract_status_id(value: Any) -> str | None:
    """Status id from a post URL or a bare id. Returns None if nothing usable."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = _STATUS_RE.search(s)
    if m:
        return m.group(1)
    # bare id; spreadsheet tools sometimes append ".0" — but reject scientific notation (precision lost)
    return s.split(".")[0] if re.fullmatch(r"\d{1,25}(\.0+)?", s) else None


def handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = _HANDLE_FROM_URL_RE.search(url)
    if m and m.group(1).lower() not in {"i", "home", "search"}:
        return m.group(1)
    return None


def norm_handle(h: str | None) -> str | None:
    if not h:
        return None
    return h.strip().lstrip("@").lower() or None


# ---------------------------------------------------------------- text length

def weighted_length(text: str) -> int:
    """X counts CJK / full-width characters as 2, most Latin as 1 (approximation)."""
    n = 0
    for ch in text or "":
        o = ord(ch)
        n += 1 if (o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037) else 2
    return n


# ---------------------------------------------------------------- loading

TREND_KEYS = {"trend", "trendname", "name", "趋势", "趋势名"}


def _sniff(sample: str) -> csv.Dialect | type[csv.Dialect]:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def read_table(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"cannot decode {path} (tried utf-8, utf-16, gb18030)")
    dialect = _sniff(text[:4096])
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or [])]
    rows = [dict(r) for r in reader]
    return headers, rows


def detect_kind(headers: list[str]) -> str:
    keys = {norm_key(h) for h in headers}
    if keys & {"postid", "tweetid", "statusid", "id", "url", "postlink", "tweetpermalink", "permalink"}:
        return "posts"
    if keys & TREND_KEYS:
        return "trends"
    return "unknown"


def load_posts(path: str | Path, overrides: dict[str, str] | None = None,
               default_tz: timezone | None = None) -> tuple[list[Record], dict[str, str], list[str]]:
    """Load one CSV → (records, column mapping, unmapped headers)."""
    headers, rows = read_table(path)
    mapping, unmapped = map_columns(headers, overrides)
    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    out: list[Record] = []
    for row in rows:
        rec: Record = {}
        for src, field in mapping.items():
            rec[field] = row.get(src)
        pid = extract_status_id(rec.get("post_id")) or extract_status_id(rec.get("url"))
        if not pid:
            continue
        rec["post_id"] = pid
        for f in METRIC_FIELDS:
            rec[f] = parse_number(rec.get(f))
        for f in ("has_link", "is_note_tweet", "is_article"):
            rec[f] = parse_bool(rec.get(f))
        rec["created_at"] = parse_time(rec.get("created_at"), default_tz)
        rec["captured_at"] = parse_time(rec.get("captured_at"), default_tz) or mtime
        if not rec.get("author"):
            rec["author"] = handle_from_url(rec.get("url"))
        rec["author"] = norm_handle(rec.get("author"))
        rec["in_reply_to_user"] = norm_handle(rec.get("in_reply_to_user"))
        for f in ("in_reply_to_id", "conversation_id", "quoted_id"):
            rec[f] = extract_status_id(rec.get(f))
        if not rec.get("url"):
            who = rec.get("author") or "i/web"
            rec["url"] = f"https://x.com/{who}/status/{pid}"
        rec["_file"] = str(path)
        out.append(rec)
    return out, mapping, unmapped


def load_many(paths: Iterable[str | Path], overrides: dict[str, str] | None = None,
              default_tz: timezone | None = None) -> list[Record]:
    recs: list[Record] = []
    for p in paths:
        r, _, _ = load_posts(p, overrides, default_tz)
        recs.extend(r)
    return recs


def merge_records(records: Iterable[Record]) -> dict[str, Record]:
    """One record per post_id. Field-wise: a newer capture's non-null value wins,
    older non-null values fill gaps (e.g. profile_visits read once from the analytics page)."""
    by_id: dict[str, list[Record]] = {}
    for r in records:
        by_id.setdefault(r["post_id"], []).append(r)
    merged: dict[str, Record] = {}
    for pid, recs in by_id.items():
        recs.sort(key=lambda r: r["captured_at"])
        m: Record = {}
        for r in recs:  # oldest → newest
            for k, v in r.items():
                if v is not None and v != "":
                    m[k] = v
        m["captured_at"] = recs[-1]["captured_at"]
        m["_files"] = sorted({r["_file"] for r in recs})
        merged[pid] = m
    return merged


# ---------------------------------------------------------------- derivations

FORMS = ("single", "thread", "long", "article", "quote", "reply")


def derive_form(rec: Record, merged: dict[str, Record] | None = None) -> str:
    f = (rec.get("form") or "").strip().lower()
    if f in FORMS:
        return f
    if rec.get("is_article"):
        return "article"
    reply_to = rec.get("in_reply_to_id")
    if reply_to:
        if rec.get("in_reply_to_user") and rec.get("in_reply_to_user") == rec.get("author"):
            return "thread"          # self-reply = thread continuation
        return "reply"
    if rec.get("quoted_id"):
        return "quote"
    if merged:
        for other in merged.values():
            if (other.get("in_reply_to_id") == rec["post_id"]
                    and other.get("author") and other.get("author") == rec.get("author")):
                return "thread"      # head of a self-thread
    if rec.get("is_note_tweet") or weighted_length(rec.get("text") or "") > 280:
        return "long"
    return "single"


def ratio(a: Any, b: Any) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def derived_metrics(rec: Record) -> dict[str, float | None]:
    imp = rec.get("impressions")
    parts = [rec.get(k) for k in ("likes", "reposts", "quotes", "replies", "bookmarks")]
    known = [p for p in parts if p is not None]
    interactions = sum(known) if known else None
    rq = None
    if rec.get("reposts") is not None or rec.get("quotes") is not None:
        rq = (rec.get("reposts") or 0) + (rec.get("quotes") or 0)
    return {
        "interaction_rate": ratio(interactions, imp),
        "engagement_rate_official": ratio(rec.get("engagements"), imp),
        "bookmark_like_ratio": ratio(rec.get("bookmarks"), rec.get("likes")),
        "reply_rate": ratio(rec.get("replies"), imp),
        "repost_quote_rate": ratio(rq, imp),
        "profile_visit_rate": ratio(rec.get("profile_visits"), imp),
        "follows_per_1k": (rec["new_follows"] / imp * 1000) if rec.get("new_follows") is not None and imp else None,
    }


def replies_to(post_id: str, merged: dict[str, Record], exclude_author: str | None = None) -> list[Record]:
    """Replies in the post's conversation, excluding the post author's own thread parts."""
    out = []
    for r in merged.values():
        if r["post_id"] == post_id:
            continue
        if r.get("in_reply_to_id") == post_id or r.get("conversation_id") == post_id:
            if exclude_author and r.get("author") == exclude_author:
                continue
            out.append(r)
    out.sort(key=lambda r: (r.get("likes") or 0), reverse=True)
    return out


def quotes_of(post_id: str, merged: dict[str, Record]) -> list[Record]:
    out = [r for r in merged.values() if r.get("quoted_id") == post_id and not r.get("in_reply_to_id")]
    out.sort(key=lambda r: (r.get("likes") or 0), reverse=True)
    return out


def median_or_none(values: Iterable[Any]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(vals) if vals else None


def hours_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return (b - a) / timedelta(hours=1)


# ---------------------------------------------------------------- trends

def load_trends(path: str | Path) -> list[Record]:
    headers, rows = read_table(path)
    keymap = {norm_key(h): h for h in headers}

    def pick(row: dict[str, str], *names: str) -> str | None:
        for n in names:
            h = keymap.get(norm_key(n))
            if h and row.get(h):
                return row[h].strip()
        return None

    out = []
    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    for row in rows:
        name = pick(row, "name", "trend", "trend_name", "趋势", "趋势名")
        if not name:
            continue
        out.append({
            "name": name,
            "meta": pick(row, "meta", "meta_description", "post_count", "帖子数"),
            "domain": pick(row, "domain", "domain_context", "category", "领域"),
            "url": pick(row, "url") or f"https://x.com/search?q={name}",
            "captured_at": parse_time(pick(row, "captured_at", "抓取时间")) or mtime,
        })
    return out
