#!/usr/bin/env python3
"""cheat-on-x CSV importer (stdlib only).

Subcommands
  find    [--project DIR] [--copy]        locate recent exports in Downloads / imports/ (metadata only)
  inspect FILE...                       show how columns map (prints NO metric values)
  text    FILE... --id ID                 print only the posted text of one post (publish check; NO metrics)
  post    FILE... --id ID --out FOLDER    write FOLDER/report.md for one post
  due     FILE... --project DIR           write report.md for every pending retro that is due
  history FILE... --handle @x             per-form medians + post list for one account (init / learn-from)
  trends  FILE                            convert a trends export into candidate JSON lines

Common options
  --map "Views=impressions,Tweet ID=post_id"   override column mapping
  --tz +08:00                                  timezone for naive timestamps (default: local)

Blindness: commands only print metrics for the posts you asked for. `history --project DIR`
skips posts that are still waiting for retro, so their numbers never reach the conversation.

Exit codes: 0 ok · 2 bad input / nothing found · 3 file problem
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aliases import CANONICAL_FIELDS, METRIC_FIELDS  # noqa: E402
from render import render_report  # noqa: E402
from xcsv import (  # noqa: E402
    derive_form, derived_metrics, detect_kind, extract_status_id, hours_between, load_posts,
    load_trends, median_or_none, merge_records, norm_handle, parse_time, quotes_of, read_table,
    replies_to,
)

TOP_LEVEL_FORMS = ("single", "thread", "long", "article", "quote")
LONGFORM = ("long", "article")


# ---------------------------------------------------------------- helpers

def parse_map(s: str | None) -> dict[str, str]:
    if not s:
        return {}
    out = {}
    for part in s.split(","):
        if "=" not in part:
            raise SystemExit(f"--map 格式应为 'col=field,col2=field2'，收到：{part}")
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_tz(s: str | None) -> timezone | None:
    if not s:
        return None
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", s.strip())
    if not m:
        raise SystemExit(f"--tz 格式应为 +08:00，收到：{s}")
    sign = 1 if m.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def load_merged(files: list[str], args: argparse.Namespace) -> dict:
    recs = []
    for f in files:
        if not Path(f).is_file():
            print(f"❌ 找不到文件：{f}", file=sys.stderr)
            raise SystemExit(3)
        r, _, _ = load_posts(f, parse_map(args.map), parse_tz(args.tz))
        recs.extend(r)
    return merge_records(recs)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def read_header(pred_path: Path) -> dict[str, str]:
    """`**Key**: value` lines above the first `## ` heading of a prediction file."""
    out: dict[str, str] = {}
    if not pred_path.is_file():
        return out
    for line in pred_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            break
        m = re.match(r"\*\*(.+?)\*\*\s*[:：]\s*(.*)$", line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def metrics_summary(rec: dict) -> dict:
    out = {k: rec.get(k) for k in METRIC_FIELDS if rec.get(k) is not None}
    out.update({k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in derived_metrics(rec).items() if v is not None})
    return out


def thread_parts_of(rec: dict, merged: dict) -> list:
    """The author's own follow-up posts in the same conversation (a thread), oldest first."""
    author = rec.get("author")
    parts = [r for r in merged.values()
             if r["post_id"] != rec["post_id"] and author and r.get("author") == author
             and r.get("conversation_id") == rec["post_id"] and r.get("in_reply_to_user") == author]
    parts.sort(key=lambda r: (r.get("created_at") or r["captured_at"], r["post_id"]))
    return parts


def write_report(rec, merged, out_dir: Path, *, source_label, published_at=None, final_path=None,
                 handle=None, form=None, window_hours=None, top=20) -> dict:
    author = rec.get("author") or norm_handle(handle)
    replies = replies_to(rec["post_id"], merged, exclude_author=author)
    quotes = quotes_of(rec["post_id"], merged)
    final_text = None
    if final_path and Path(final_path).is_file():
        final_text = Path(final_path).read_text(encoding="utf-8")
    form = form or derive_form(rec, merged)
    md = render_report(rec, source_label=source_label, published_at=published_at, replies=replies,
                       quotes=quotes, final_text=final_text, top_n=top, form=form,
                       window_hours=window_hours, thread_parts=thread_parts_of(rec, merged))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    age = hours_between(published_at or rec.get("created_at"), rec.get("captured_at"))
    return {
        "post_id": rec["post_id"],
        "report": str(out_dir / "report.md"),
        "form": form,
        "snapshot_age_hours": round(age, 1) if age is not None else None,
        "early_snapshot": bool(window_hours and age is not None and age < window_hours),
        "replies_captured": len(replies),
        "quotes_captured": len(quotes),
        "metrics": metrics_summary(rec),
    }


def source_label_for(files: list[str], label: str | None) -> str:
    names = "、".join(os.path.basename(f) for f in files)
    return f"{label or 'csv'}（{names}）"


# ---------------------------------------------------------------- commands

def cmd_inspect(args) -> int:
    from aliases import map_columns
    for f in args.files:
        if not Path(f).is_file():
            print(f"❌ 找不到文件：{f}", file=sys.stderr)
            return 3
        headers, rows = read_table(f)
        kind = detect_kind(headers)
        mapping, unmapped = map_columns(headers, parse_map(args.map))
        print(f"== {f}")
        print(f"   类型：{kind} · {len(rows)} 行")
        if kind == "trends":
            print(f"   列：{', '.join(headers)}")
            continue
        print("   列映射：")
        for src, field in mapping.items():
            print(f"     {src!r:32} → {field}")
        if unmapped:
            print(f"   未识别的列：{', '.join(repr(u) for u in unmapped)}")
            print("     需要的话用 --map '列名=字段' 指定。可用字段：" + ", ".join(CANONICAL_FIELDS))
        missing = [k for k in ("post_id", "impressions", "likes", "text") if k not in mapping.values()]
        if "post_id" in missing and "url" in mapping.values():
            missing.remove("post_id")
        if missing:
            print(f"   ⚠️ 缺少关键字段：{', '.join(missing)}")
        recs, _, _ = load_posts(f, parse_map(args.map), parse_tz(args.tz))
        authors = {r.get("author") for r in recs if r.get("author")}
        print(f"   可识别帖子：{len(recs)} 条 · 作者数：{len(authors)}")
    return 0


def default_search_dirs(project: Path | None) -> list[Path]:
    """Where browser downloads usually land, plus the project's own imports/."""
    home = Path.home()
    dirs = []
    if project:
        dirs.append(project / "imports")
    for name in ("Downloads", "下载", "downloads"):
        dirs.append(home / name)
    for env in ("USERPROFILE", "XDG_DOWNLOAD_DIR"):
        v = os.environ.get(env)
        if v:
            dirs.append(Path(v) / "Downloads" if env == "USERPROFILE" else Path(v))
    seen, out = set(), []
    for d in dirs:
        try:
            key = os.path.normcase(str(d.resolve()))
        except OSError:
            continue
        if key not in seen and d.is_dir():
            seen.add(key)
            out.append(d)
    return out


def classify_file(path: Path, own_handle: str | None, args) -> dict | None:
    """Metadata about one CSV — counts only, never metric values (blind-safe)."""
    from aliases import map_columns
    try:
        headers, rows = read_table(path)
    except (ValueError, OSError):
        return None
    kind = detect_kind(headers)
    info = {"kind": kind, "rows": len(rows)}
    if kind == "posts":
        mapping, _ = map_columns(headers, parse_map(args.map))
        if not ({"impressions", "likes"} & set(mapping.values())):
            info["kind"] = "unknown"
            return info
        recs, _, _ = load_posts(path, parse_map(args.map), parse_tz(args.tz))
        authors = {r.get("author") for r in recs if r.get("author")}
        info["posts"] = len(recs)
        info["authors"] = len(authors)
        if own_handle:
            info["mine"] = sum(1 for r in recs if r.get("author") == own_handle)
    return info


def cmd_find(args) -> int:
    project = Path(args.project) if args.project else None
    own = norm_handle(args.handle)
    if not own and project and (project / ".cheatx-state.json").is_file():
        try:
            own = norm_handle(json.loads((project / ".cheatx-state.json").read_text(encoding="utf-8")).get("x_handle"))
        except (OSError, ValueError):
            own = None
    dirs = [Path(d) for d in args.dir] if args.dir else default_search_dirs(project)
    cutoff = datetime.now().timestamp() - args.days * 86400
    found = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if not f.is_file() or f.suffix.lower() != ".csv":
                continue
            st = f.stat()
            if st.st_mtime < cutoff:
                continue
            ours = f.name.startswith("cheatx-")
            info = classify_file(f, own, args)
            if info is None or (info["kind"] == "unknown" and not ours):
                continue   # unrelated CSV in Downloads — not ours to touch
            item = {"path": str(f), "name": f.name, "dir": str(d),
                    "modified": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="minutes"),
                    "size": st.st_size, "from_userscript": ours, **info}
            found.append(item)
    found.sort(key=lambda x: x["modified"], reverse=True)
    if args.copy and project:
        dest = project / "imports"
        dest.mkdir(parents=True, exist_ok=True)
        for item in found:
            src = Path(item["path"])
            if os.path.normcase(str(src.parent.resolve())) == os.path.normcase(str(dest.resolve())):
                item["project_path"] = str(Path("imports") / src.name)
                continue
            target = dest / src.name
            if target.exists() and target.stat().st_size == src.stat().st_size:
                item["project_path"] = str(Path("imports") / src.name)
                item["copied"] = False
                continue
            if target.exists():
                target = dest / f"{src.stem}-{int(src.stat().st_mtime)}{src.suffix}"
            target.write_bytes(src.read_bytes())   # copy, never move: the user's Downloads stay as they were
            item["project_path"] = str(Path("imports") / target.name)
            item["copied"] = True
    emit({"searched": [str(d) for d in dirs], "days": args.days, "files": found})
    return 0 if found else 2


def cmd_text(args) -> int:
    pid = extract_status_id(args.id)
    merged = load_merged(args.files, args)
    rec = merged.get(pid or "")
    if not rec:
        emit({"post_id": pid, "found": False})
        return 2
    author = rec.get("author")
    parts = thread_parts_of(rec, merged)
    thread_text = "\n\n".join([rec.get("text") or ""] + [p.get("text") or "" for p in parts]) if parts else None
    emit({"post_id": pid, "found": True, "author": author, "created_at": rec.get("created_at"),
          "text": rec.get("text"), "thread_parts": len(parts), "thread_text": thread_text})
    return 0


def cmd_post(args) -> int:
    pid = extract_status_id(args.id)
    if not pid:
        print(f"❌ 无法从 {args.id!r} 解析出 status id", file=sys.stderr)
        return 2
    merged = load_merged(args.files, args)
    rec = merged.get(pid)
    if not rec:
        print(f"❌ 导出文件里没有 {pid}。确认导出时打开过这条帖子（主页列表或详情页）。", file=sys.stderr)
        return 2
    published = parse_time(args.published_at) if args.published_at else None
    summary = write_report(rec, merged, Path(args.out), source_label=source_label_for(args.files, args.label),
                           published_at=published, final_path=args.final, handle=args.handle,
                           form=args.form, window_hours=args.window_hours, top=args.top)
    emit(summary)
    return 0


def cmd_due(args) -> int:
    project = Path(args.project)
    state_path = project / ".cheatx-state.json"
    if not state_path.is_file():
        print(f"❌ {project} 不是 cheat-on-x 项目（没有 .cheatx-state.json）", file=sys.stderr)
        return 3
    state = json.loads(state_path.read_text(encoding="utf-8"))
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc).astimezone()
    merged = load_merged(args.files, args)
    handle = args.handle or state.get("x_handle")
    w_short = state.get("retro_window_hours", 48)
    w_long = state.get("retro_window_hours_longform", 168)
    results, not_due = [], 0
    for item in state.get("pending_retros", []):
        if isinstance(item, str):
            item = {"file": item}
        pred = project / item["file"]
        header = read_header(pred)
        pid = item.get("status_id") or extract_status_id(header.get("Status ID") or header.get("URL"))
        published = parse_time(item.get("published_at") or header.get("Published at"))
        form = item.get("form") or (header.get("Form") or "").split(" ")[0] or None
        window = w_long if form in LONGFORM else w_short
        due_at = parse_time(item.get("due_at")) or (published + timedelta(hours=window) if published else None)
        if due_at and due_at > now and not args.include_early:
            not_due += 1
            continue
        entry = {"prediction_file": item["file"], "status_id": pid, "due_at": due_at}
        rec = merged.get(pid or "")
        if not rec:
            entry["found"] = False
            entry["hint"] = "导出里没有这条：在 x.com 打开它（或滚到它）后重新导出"
            results.append(entry)
            continue
        folder_rel = (header.get("Post Folder") or "").strip().strip("`") or f"posts/{pred.stem}/"
        out_dir = project / folder_rel
        final = out_dir / "final.md"
        summary = write_report(rec, merged, out_dir, source_label=source_label_for(args.files, args.label),
                               published_at=published, final_path=final, handle=handle,
                               form=form, window_hours=window, top=args.top)
        summary["prediction_file"] = item["file"]
        summary["found"] = True
        summary["early"] = bool(due_at and due_at > now)
        results.append(summary)
    emit({"now": now, "processed": results, "not_yet_due": not_due})
    return 0 if results else 2


def cmd_history(args) -> int:
    handle = norm_handle(args.handle)
    merged = load_merged(args.files, args)
    skip_ids: set[str] = set()
    if args.project:
        sp = Path(args.project) / ".cheatx-state.json"
        if sp.is_file():
            st = json.loads(sp.read_text(encoding="utf-8"))
            for item in st.get("pending_retros", []):
                if isinstance(item, dict) and item.get("status_id"):
                    skip_ids.add(str(item["status_id"]))
                else:
                    hdr = read_header(Path(args.project) / (item["file"] if isinstance(item, dict) else item))
                    sid = extract_status_id(hdr.get("Status ID") or hdr.get("URL"))
                    if sid:
                        skip_ids.add(sid)
    posts = [r for r in merged.values() if r.get("author") == handle]
    skipped = [r for r in posts if r["post_id"] in skip_ids]
    posts = [r for r in posts if r["post_id"] not in skip_ids]
    for r in posts:
        r["_form"] = derive_form(r, merged)
    if not args.include_replies:
        posts = [r for r in posts if r["_form"] != "reply"]
    posts = [r for r in posts if not (r["_form"] == "thread" and r.get("in_reply_to_id"))]  # keep thread heads only
    posts.sort(key=lambda r: r.get("created_at") or r["captured_at"], reverse=True)
    if args.limit:
        posts = posts[: args.limit]
    by_form: dict[str, list] = {}
    for r in posts:
        by_form.setdefault(r["_form"], []).append(r.get("impressions"))
    medians = {f: median_or_none(v) for f, v in by_form.items()}
    overall = median_or_none(r.get("impressions") for r in posts)
    out_posts = []
    for r in posts:
        imp = r.get("impressions")
        rel = (imp / overall) if (imp is not None and overall) else None
        tier = None
        if rel is not None:
            tier = "高" if rel >= 2 else ("低" if rel <= 0.5 else "中")
        out_posts.append({
            "post_id": r["post_id"], "url": r.get("url"), "created_at": r.get("created_at"),
            "form": r["_form"], "impressions": imp, "likes": r.get("likes"), "reposts": r.get("reposts"),
            "quotes": r.get("quotes"), "replies": r.get("replies"), "bookmarks": r.get("bookmarks"),
            "ratio_to_median": round(rel, 2) if rel is not None else None, "tier": tier,
            "text_preview": (r.get("text") or "")[:80],
        })
        if args.samples_dir:
            d = Path(args.samples_dir)
            d.mkdir(parents=True, exist_ok=True)
            meta = [f"# {r['post_id']}", "",
                    f"- **URL**: {r.get('url')}", f"- **Created**: {r.get('created_at')}",
                    f"- **Form**: {r['_form']}", f"- **Impressions**: {imp}",
                    f"- **Ratio to account median**: {out_posts[-1]['ratio_to_median']}",
                    f"- **Tier**: {tier}", "", "## 正文", "", r.get("text") or "（导出未包含正文）", ""]
            (d / f"{r['post_id']}.md").write_text("\n".join(meta), encoding="utf-8")
    emit({"handle": handle, "count": len(out_posts), "median_impressions": overall,
          "median_by_form": medians, "skipped_pending_retro": len(skipped), "posts": out_posts})
    return 0 if out_posts else 2


def cmd_trends(args) -> int:
    items = load_trends(args.file)
    for t in items:
        title = t["name"]
        url_path = t["url"].split("?")[0].rstrip("/")
        cid = hashlib.sha256(f"trend|{title.strip().lower().replace(' ', '')}|{url_path}".encode()).hexdigest()[:12]
        snap = " · ".join(x for x in (title, t.get("meta"), t.get("domain")) if x)
        print(json.dumps({
            "id": cid, "title": f"（X 趋势）{title}", "source": "trend:x-trends", "snapshot_text": snap,
            "snapshot_at": t["captured_at"].isoformat(), "url": t["url"],
            "expires_at": (t["captured_at"] + timedelta(hours=24)).isoformat(),
            "category": t.get("domain"), "composite_score": None, "dimension_scores": None,
        }, ensure_ascii=False))
    return 0 if items else 2


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map", help="列映射覆盖：'Views=impressions,Tweet ID=post_id'")
    p.add_argument("--tz", help="无时区时间的时区，如 +08:00（默认本机时区）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("find", help="找最近导出的 CSV（下载文件夹 + imports/），只给元数据")
    s.add_argument("--project", help="项目目录；会搜它的 imports/，并从 state 读你的 handle")
    s.add_argument("--dir", action="append", help="只搜这些目录（可重复）；默认下载文件夹 + imports/")
    s.add_argument("--days", type=float, default=14, help="只看最近 N 天修改的文件（默认 14）")
    s.add_argument("--handle", help="你的 handle，用来数文件里有几条是你的帖子")
    s.add_argument("--copy", action="store_true", help="把找到的文件复制进 <project>/imports/（不移动原文件）")

    s = sub.add_parser("inspect")
    s.add_argument("files", nargs="+")

    s = sub.add_parser("text")
    s.add_argument("files", nargs="+")
    s.add_argument("--id", required=True)

    s = sub.add_parser("post")
    s.add_argument("files", nargs="+")
    s.add_argument("--id", required=True, help="status id 或帖子链接")
    s.add_argument("--out", required=True, help="posts/<id>/ 目录")
    s.add_argument("--published-at")
    s.add_argument("--final", help="posts/<id>/final.md")
    s.add_argument("--handle")
    s.add_argument("--form")
    s.add_argument("--window-hours", type=int)
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--label", help="数据来源标签，如 csv:userscript / csv:x-analytics")

    s = sub.add_parser("due")
    s.add_argument("files", nargs="+")
    s.add_argument("--project", required=True)
    s.add_argument("--now")
    s.add_argument("--include-early", action="store_true")
    s.add_argument("--handle")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--label")

    s = sub.add_parser("history")
    s.add_argument("files", nargs="+")
    s.add_argument("--handle", required=True)
    s.add_argument("--project", help="跳过该项目里仍待复盘的帖子（保盲）")
    s.add_argument("--limit", type=int)
    s.add_argument("--include-replies", action="store_true")
    s.add_argument("--samples-dir", help="把每条正文写到 samples/<handle>/<id>.md")

    s = sub.add_parser("trends")
    s.add_argument("file")

    args = p.parse_args(argv)
    try:
        return {"find": cmd_find, "inspect": cmd_inspect, "text": cmd_text, "post": cmd_post, "due": cmd_due,
                "history": cmd_history, "trends": cmd_trends}[args.cmd](args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
