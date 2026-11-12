#!/usr/bin/env python3
"""cheat-on-x — optional X API v2 fetcher (stdlib only, pay-per-use).

It fetches posts / replies / quotes / timelines / trends from the official X API, writes them as
a canonical CSV under .cheatx-cache/x-api/, then hands that CSV to x-csv-import — so reports,
batch retros and history work exactly like the userscript route.

Every networked command is a DRY RUN unless you pass --yes: it prints the planned calls and an
estimated cost, and sends nothing.

Subcommands
  estimate                                 print the price table used for estimates
  text    ID                               posted text only (no metrics requested) — publish check
  post    ID --out FOLDER [--replies N] [--quotes N] [--user-context] [--published-at ISO] [--final PATH]
  due     --project DIR [--replies N]      every pending retro that is due
  history HANDLE [--limit N] [--samples-dir DIR] [--project DIR]
  trends  [--woeid 1]

Tokens (never stored in .cheatx-state.json):
  env X_BEARER_TOKEN / X_USER_ACCESS_TOKEN, or <project>/.cheatx-secrets.json
  {"x_bearer_token": "...", "x_user_access_token": "..."}

Exit codes: 0 ok · 1 auth problem · 2 bad input · 3 network/API error · 4 rate limited · 5 dry run only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
IMPORTER_DIR = HERE.parent / "x-csv-import"
sys.path.insert(0, str(IMPORTER_DIR))

import import_csv  # noqa: E402
from xcsv import (  # noqa: E402
    TREND_CSV_HEADER, extract_status_id, norm_handle, parse_time, write_canonical_csv,
)

API = "https://api.x.com/2"
USER_AGENT = "cheat-on-x/0.1"

# Unit prices used for ESTIMATES only. Source: third-party summaries of X's pay-per-use pricing
# (2026). X bills per resource returned. Check https://docs.x.com for the current rate card and
# update these numbers — they are not authoritative.
PRICE_USD = {
    "post_read": 0.005,     # each post returned (tweet lookup, search, timeline, quotes)
    "user_read": 0.010,     # each user returned (username lookup)
    "trends": None,         # not published in the summaries we found — shown as unknown
}

# Only documented tweet.fields: an unknown field makes the whole request fail with 400.
TWEET_FIELDS = ("created_at,public_metrics,conversation_id,in_reply_to_user_id,referenced_tweets,"
                "note_tweet,lang,entities,attachments,author_id")
EXPANSIONS = "author_id,attachments.media_keys,in_reply_to_user_id"
USER_FIELDS = "username"
MEDIA_FIELDS = "type"


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- tokens

def load_tokens(project: Path | None) -> dict[str, str | None]:
    tok = {"bearer": os.environ.get("X_BEARER_TOKEN"), "user": os.environ.get("X_USER_ACCESS_TOKEN")}
    if project:
        sec = project / ".cheatx-secrets.json"
        if sec.is_file():
            data = json.loads(sec.read_text(encoding="utf-8"))
            tok["bearer"] = tok["bearer"] or data.get("x_bearer_token")
            tok["user"] = tok["user"] or data.get("x_user_access_token")
    return tok


# ---------------------------------------------------------------- http

Opener = Callable[[urllib.request.Request], Any]


def _default_opener(req: urllib.request.Request):
    return urllib.request.urlopen(req, timeout=30)


def api_get(path: str, params: dict[str, Any], token: str, opener: Opener = _default_opener) -> dict:
    url = f"{API}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    try:
        with opener(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code == 429:
            reset = e.headers.get("x-rate-limit-reset") if e.headers else None
            when = datetime.fromtimestamp(int(reset), tz=timezone.utc).astimezone().isoformat() if reset else "未知"
            raise ApiError(4, f"触发限流（429），重置时间 {when}。不自动重试。") from e
        if e.code in (401, 403):
            raise ApiError(1, f"鉴权失败（{e.code}）：token 无效、权限不够或该端点不在你的套餐里。{body}") from e
        raise ApiError(3, f"API 错误 {e.code}：{body}") from e
    except urllib.error.URLError as e:
        raise ApiError(3, f"网络错误：{e.reason}") from e


# ---------------------------------------------------------------- mapping

def record_from_api(t: dict, includes: dict | None, captured_at: datetime) -> dict:
    """X API v2 tweet object → canonical record (same columns as the userscript CSV)."""
    includes = includes or {}
    users = {u["id"]: u.get("username") for u in includes.get("users", [])}
    media = {m["media_key"]: m.get("type") for m in includes.get("media", [])}
    pm = t.get("public_metrics") or {}
    npm = t.get("non_public_metrics") or {}
    om = t.get("organic_metrics") or {}
    refs = {r.get("type"): r.get("id") for r in t.get("referenced_tweets") or []}
    author = users.get(t.get("author_id"))
    urls = [u.get("expanded_url") or u.get("url") or "" for u in (t.get("entities") or {}).get("urls", [])]
    ext = [u for u in urls if u and "/status/" not in u]
    mkeys = (t.get("attachments") or {}).get("media_keys") or []
    note = (t.get("note_tweet") or {}).get("text")
    return {
        "post_id": t["id"],
        "url": f"https://x.com/{author or 'i/web'}/status/{t['id']}",
        "author": author,
        "created_at": t.get("created_at"),
        "captured_at": captured_at.isoformat(),
        "form": "",
        "text": note or t.get("text") or "",
        "impressions": npm.get("impression_count", om.get("impression_count", pm.get("impression_count"))),
        "likes": pm.get("like_count"),
        "reposts": pm.get("retweet_count"),
        "quotes": pm.get("quote_count"),
        "replies": pm.get("reply_count"),
        "bookmarks": pm.get("bookmark_count"),
        "engagements": npm.get("engagements"),
        "profile_visits": npm.get("user_profile_clicks", om.get("user_profile_clicks")),
        "new_follows": None,
        "link_clicks": npm.get("url_link_clicks", om.get("url_link_clicks")),
        "detail_expands": None, "media_views": None, "shares": None,
        "has_link": bool(ext),
        "media": "|".join(sorted({media.get(k) for k in mkeys if media.get(k)})),
        "lang": t.get("lang"),
        "in_reply_to_id": refs.get("replied_to"),
        "in_reply_to_user": users.get(t.get("in_reply_to_user_id")),
        "conversation_id": t.get("conversation_id"),
        "quoted_id": refs.get("quoted"),
        "is_note_tweet": bool(note),
        "is_article": bool(t.get("article")),
        "source": "x-api",
    }


def records_from_response(resp: dict, captured_at: datetime) -> list[dict]:
    data = resp.get("data")
    if data is None:
        return []
    items = data if isinstance(data, list) else [data]
    return [record_from_api(t, resp.get("includes"), captured_at) for t in items]


# ---------------------------------------------------------------- planning / cost

def estimate(calls: list[tuple[str, str, int]]) -> tuple[float | None, list[str]]:
    """calls: (description, price_key, max_units) → (total USD or None if unknown, lines)."""
    total: float | None = 0.0
    lines = []
    for desc, key, units in calls:
        price = PRICE_USD.get(key)
        if price is None:
            total = None
            lines.append(f"  · {desc}：单价未知")
        else:
            cost = price * units
            if total is not None:
                total += cost
            lines.append(f"  · {desc}：最多 {units} 个 × ${price:.3f} = ${cost:.3f}")
    return total, lines


def print_plan(calls, live: bool) -> None:
    total, lines = estimate(calls)
    print("计划调用（X API v2，按量计费）：", file=sys.stderr)
    for line in lines:
        print(line, file=sys.stderr)
    print(f"  预估上限：{'未知' if total is None else f'${total:.3f}'}（单价来自第三方汇总，以 docs.x.com 为准）",
          file=sys.stderr)
    if not live:
        print("  这是预演，没有发出任何请求。确认后加 --yes 执行。", file=sys.stderr)


def cache_dir(project: Path) -> Path:
    d = project / ".cheatx-cache" / "x-api"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------------------------------------------------------------- fetchers

def fetch_post_bundle(pid: str, token: str, *, user_token: str | None, replies: int, quotes: int,
                      opener: Opener = _default_opener) -> list[dict]:
    now = datetime.now(timezone.utc)
    fields = TWEET_FIELDS + (",non_public_metrics,organic_metrics" if user_token else "")
    head = api_get(f"/tweets/{pid}", {"tweet.fields": fields, "expansions": EXPANSIONS,
                                       "user.fields": USER_FIELDS, "media.fields": MEDIA_FIELDS},
                   user_token or token, opener)
    rows = records_from_response(head, now)
    if not rows:
        raise ApiError(2, f"API 没有返回帖子 {pid}（可能已删除或不可见）")
    conv = rows[0].get("conversation_id") or pid
    if replies > 0:
        r = api_get("/tweets/search/recent", {
            "query": f"conversation_id:{conv} is:reply", "max_results": max(10, min(100, replies)),
            "tweet.fields": TWEET_FIELDS, "expansions": "author_id,in_reply_to_user_id",
            "user.fields": USER_FIELDS}, token, opener)
        rows += records_from_response(r, now)
    if quotes > 0:
        q = api_get(f"/tweets/{pid}/quote_tweets", {
            "max_results": max(10, min(100, quotes)), "tweet.fields": TWEET_FIELDS,
            "expansions": "author_id", "user.fields": USER_FIELDS}, token, opener)
        rows += records_from_response(q, now)
    return rows


def fetch_timeline(handle: str, token: str, limit: int, include_replies: bool,
                   opener: Opener = _default_opener) -> list[dict]:
    now = datetime.now(timezone.utc)
    u = api_get(f"/users/by/username/{handle}", {"user.fields": "public_metrics"}, token, opener)
    uid = (u.get("data") or {}).get("id")
    if not uid:
        raise ApiError(2, f"找不到用户 @{handle}")
    rows: list[dict] = []
    token_next = None
    while len(rows) < limit:
        params = {"max_results": max(5, min(100, limit - len(rows))), "tweet.fields": TWEET_FIELDS,
                  "expansions": EXPANSIONS, "user.fields": USER_FIELDS, "media.fields": MEDIA_FIELDS,
                  "exclude": "retweets" if include_replies else "retweets,replies",
                  "pagination_token": token_next}
        resp = api_get(f"/users/{uid}/tweets", params, token, opener)
        rows += records_from_response(resp, now)
        token_next = (resp.get("meta") or {}).get("next_token")
        if not token_next:
            break
    return rows[:limit]


# ---------------------------------------------------------------- commands

def require_bearer(tokens) -> str:
    if not tokens["bearer"]:
        print("❌ 没有 X API Bearer Token。设置环境变量 X_BEARER_TOKEN，或在项目根 .cheatx-secrets.json 写 "
              '{"x_bearer_token": "..."}（该文件已在 .gitignore 里）。', file=sys.stderr)
        raise SystemExit(1)
    return tokens["bearer"]


def cmd_estimate(args) -> int:
    for k, v in PRICE_USD.items():
        print(f"{k}: {'未知' if v is None else f'${v:.3f}'}")
    print("单价来自第三方汇总（2026），以 https://docs.x.com 定价页为准；可直接改 xapi.py 的 PRICE_USD。")
    return 0


def cmd_text(args, opener: Opener = _default_opener) -> int:
    pid = extract_status_id(args.id)
    if not pid:
        print(f"❌ 无法解析 status id：{args.id}", file=sys.stderr)
        return 2
    print_plan([("帖子正文（不请求任何指标字段）", "post_read", 1)], args.yes)
    if not args.yes:
        return 5
    token = require_bearer(load_tokens(Path(args.project)))
    resp = api_get(f"/tweets/{pid}", {"tweet.fields": "created_at,note_tweet,author_id",
                                       "expansions": "author_id", "user.fields": "username"}, token, opener)
    t = resp.get("data")
    if not t:
        print(json.dumps({"post_id": pid, "found": False}, ensure_ascii=False))
        return 2
    users = {u["id"]: u.get("username") for u in (resp.get("includes") or {}).get("users", [])}
    print(json.dumps({"post_id": pid, "found": True, "author": users.get(t.get("author_id")),
                      "created_at": t.get("created_at"),
                      "text": (t.get("note_tweet") or {}).get("text") or t.get("text")}, ensure_ascii=False, indent=2))
    return 0


def cmd_post(args, opener: Opener = _default_opener) -> int:
    pid = extract_status_id(args.id)
    if not pid:
        print(f"❌ 无法解析 status id：{args.id}", file=sys.stderr)
        return 2
    calls = [("帖子本身", "post_read", 1)]
    if args.replies:
        calls.append((f"回复（近 7 天搜索，最多 {args.replies} 条）", "post_read", max(10, min(100, args.replies))))
    if args.quotes:
        calls.append((f"引用（最多 {args.quotes} 条）", "post_read", max(10, min(100, args.quotes))))
    print_plan(calls, args.yes)
    if not args.yes:
        return 5
    project = Path(args.project)
    tokens = load_tokens(project)
    bearer = require_bearer(tokens)
    rows = fetch_post_bundle(pid, bearer, user_token=tokens["user"] if args.user_context else None,
                             replies=args.replies, quotes=args.quotes, opener=opener)
    csv_path = write_canonical_csv(cache_dir(project) / f"post-{pid}-{stamp()}.csv", rows)
    argv = ["post", str(csv_path), "--id", pid, "--out", args.out, "--label", "x-api", "--top", str(args.top)]
    for flag, val in (("--published-at", args.published_at), ("--final", args.final),
                      ("--window-hours", args.window_hours), ("--form", args.form)):
        if val:
            argv += [flag, str(val)]
    return import_csv.main(argv)


def due_items(project: Path, now: datetime) -> list[dict]:
    state = json.loads((project / ".cheatx-state.json").read_text(encoding="utf-8"))
    out = []
    for item in state.get("pending_retros", []):
        if isinstance(item, str):
            item = {"file": item}
        hdr = import_csv.read_header(project / item["file"])
        pid = item.get("status_id") or extract_status_id(hdr.get("Status ID") or hdr.get("URL"))
        due_at = parse_time(item.get("due_at"))
        if pid and (due_at is None or due_at <= now):
            out.append({"status_id": pid, **item})
    return out


def cmd_due(args, opener: Opener = _default_opener) -> int:
    project = Path(args.project)
    if not (project / ".cheatx-state.json").is_file():
        print(f"❌ {project} 不是 cheat-on-x 项目", file=sys.stderr)
        return 3
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    items = due_items(project, now)
    if not items:
        print("没有到期的复盘。", file=sys.stderr)
        return 2
    per = 1 + (max(10, min(100, args.replies)) if args.replies else 0)
    print_plan([(f"{len(items)} 条到期帖子（每条：本身 + 回复）", "post_read", per * len(items))], args.yes)
    if not args.yes:
        return 5
    tokens = load_tokens(project)
    bearer = require_bearer(tokens)
    rows: list[dict] = []
    for it in items:
        rows += fetch_post_bundle(it["status_id"], bearer, user_token=tokens["user"] if args.user_context else None,
                                  replies=args.replies, quotes=0, opener=opener)
    csv_path = write_canonical_csv(cache_dir(project) / f"due-{stamp()}.csv", rows)
    argv = ["due", str(csv_path), "--project", str(project), "--label", "x-api"]
    if args.now:
        argv += ["--now", args.now]
    return import_csv.main(argv)


def cmd_history(args, opener: Opener = _default_opener) -> int:
    handle = norm_handle(args.handle)
    print_plan([("用户查询", "user_read", 1), (f"@{handle} 最近 {args.limit} 条帖子", "post_read", args.limit)], args.yes)
    if not args.yes:
        return 5
    project = Path(args.project or ".")
    bearer = require_bearer(load_tokens(project))
    rows = fetch_timeline(handle, bearer, args.limit, args.include_replies, opener)
    csv_path = write_canonical_csv(cache_dir(project) / f"history-{handle}-{stamp()}.csv", rows)
    argv = ["history", str(csv_path), "--handle", handle]
    if args.project:
        argv += ["--project", args.project]
    if args.samples_dir:
        argv += ["--samples-dir", args.samples_dir]
    if args.include_replies:
        argv.append("--include-replies")
    return import_csv.main(argv)


def cmd_trends(args, opener: Opener = _default_opener) -> int:
    print_plan([(f"趋势（WOEID {args.woeid}）", "trends", 1)], args.yes)
    if not args.yes:
        return 5
    project = Path(args.project)
    bearer = require_bearer(load_tokens(project))
    resp = api_get(f"/trends/by/woeid/{args.woeid}", {"max_trends": 50}, bearer, opener)
    now = datetime.now(timezone.utc).isoformat()
    rows = [{"name": t.get("trend_name"), "meta": f"{t['tweet_count']} posts" if t.get("tweet_count") else None,
             "domain": None, "url": f"https://x.com/search?q={urllib.parse.quote(t.get('trend_name') or '')}",
             "captured_at": now} for t in resp.get("data") or [] if t.get("trend_name")]
    csv_path = write_canonical_csv(cache_dir(project) / f"trends-{stamp()}.csv", rows, TREND_CSV_HEADER)
    return import_csv.main(["trends", str(csv_path)])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, project_default="."):
        s.add_argument("--project", default=project_default, help="X 内容项目根目录（找 .cheatx-secrets.json）")
        s.add_argument("--yes", action="store_true", help="确认按预估费用执行；不加只预演")

    sub.add_parser("estimate")
    s = sub.add_parser("text"); s.add_argument("id"); common(s)
    s = sub.add_parser("post"); s.add_argument("id"); common(s)
    s.add_argument("--out", required=True)
    s.add_argument("--replies", type=int, default=20)
    s.add_argument("--quotes", type=int, default=0)
    s.add_argument("--user-context", action="store_true", help="用用户授权 token 取主页点击 / 链接点击（仅本人 30 天内帖子）")
    s.add_argument("--published-at"); s.add_argument("--final"); s.add_argument("--form")
    s.add_argument("--window-hours", type=int); s.add_argument("--top", type=int, default=20)
    s = sub.add_parser("due"); common(s)
    s.add_argument("--replies", type=int, default=20)
    s.add_argument("--user-context", action="store_true")
    s.add_argument("--now")
    s = sub.add_parser("history"); s.add_argument("handle"); common(s, project_default=None)
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--include-replies", action="store_true")
    s.add_argument("--samples-dir")
    s = sub.add_parser("trends"); common(s)
    s.add_argument("--woeid", type=int, default=1, help="1=全球，23424977=美国 …")
    return p


def main(argv: list[str] | None = None, opener: Opener = _default_opener) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"estimate": lambda a: cmd_estimate(a), "text": cmd_text, "post": cmd_post, "due": cmd_due,
                "history": cmd_history, "trends": cmd_trends}
    try:
        if args.cmd == "estimate":
            return cmd_estimate(args)
        return handlers[args.cmd](args, opener)
    except ApiError as e:
        print(f"❌ {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
