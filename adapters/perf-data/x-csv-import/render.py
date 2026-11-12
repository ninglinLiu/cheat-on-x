"""Render a canonical post record into posts/<id>/report.md (shared by x-csv-import and x-api)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from xcsv import Record, derived_metrics, hours_between

METRIC_LABELS = [
    ("impressions", "曝光"),
    ("likes", "赞"),
    ("reposts", "转发"),
    ("quotes", "引用"),
    ("replies", "回复"),
    ("bookmarks", "收藏"),
    ("engagements", "互动（官方口径）"),
    ("profile_visits", "主页访问"),
    ("new_follows", "新增关注"),
    ("link_clicks", "链接点击"),
    ("detail_expands", "展开详情"),
    ("media_views", "媒体浏览"),
    ("shares", "分享"),
]

RATIO_LABELS = [
    ("interaction_rate", "互动率", "(赞+转+引用+回复+收藏) ÷ 曝光", True),
    ("engagement_rate_official", "官方互动率", "互动 ÷ 曝光", True),
    ("bookmark_like_ratio", "收藏/赞比", "收藏 ÷ 赞（SV 的外部代理）", False),
    ("reply_rate", "回复率", "回复 ÷ 曝光（RP 的外部代理）", True),
    ("repost_quote_rate", "转引率", "(转+引用) ÷ 曝光（RS 的外部代理）", True),
    ("profile_visit_rate", "主页访问率", "主页访问 ÷ 曝光（FT 的外部代理）", True),
    ("follows_per_1k", "每千曝光新增关注", "新增关注 ÷ 曝光 × 1000", False),
]


def fmt_int(v: Any) -> str:
    if v is None:
        return "—（数据源未提供）"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}"
    return f"{int(v):,}"


def fmt_ratio(v: float | None, pct: bool) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.2f}%" if pct else f"{v:.2f}"


def fmt_time(dt: datetime | None) -> str:
    return dt.astimezone().isoformat(timespec="minutes") if dt else "—"   # local time, same zone everywhere


def quote_block(text: str | None) -> str:
    if not text:
        return "> （数据源未包含正文）"
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def render_report(rec: Record, *, source_label: str, published_at: datetime | None = None,
                  replies: list[Record] | None = None, quotes: list[Record] | None = None,
                  final_text: str | None = None, top_n: int = 20, form: str | None = None,
                  window_hours: int | None = None, thread_parts: list[Record] | None = None) -> str:
    published = published_at or rec.get("created_at")
    age = hours_between(published, rec.get("captured_at"))
    replies = replies or []
    quotes = quotes or []
    lines: list[str] = []
    lines.append(f"# 帖子数据报告 — {rec['post_id']}")
    lines.append("")
    lines.append(f"- **Status ID**: {rec['post_id']}")
    lines.append(f"- **URL**: {rec.get('url') or '—'}")
    if form:
        lines.append(f"- **形态**: {form}")
    lines.append(f"- **发布时间**: {fmt_time(published)}")
    snap = f"{fmt_time(rec.get('captured_at'))}"
    if age is not None:
        snap += f"（距发布 {age:.1f}h）"
    lines.append(f"- **数据快照时间**: {snap}")
    if window_hours and age is not None and age < window_hours:
        lines.append(f"- ⚠️ **early_snapshot**: 快照早于复盘窗口（{age:.1f}h < {window_hours}h），数字可能还在涨")
    lines.append(f"- **数据来源**: {source_label}")
    lines.append("")
    lines.append("## 数据快照")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    for key, label in METRIC_LABELS:
        if key in ("engagements", "profile_visits", "new_follows", "link_clicks",
                   "detail_expands", "media_views", "shares") and rec.get(key) is None:
            continue  # only show optional metrics the source actually had
        lines.append(f"| {label} | {fmt_int(rec.get(key))} |")
    lines.append("")
    lines.append("## 派生比率")
    lines.append("")
    lines.append("| 比率 | 数值 | 口径 |")
    lines.append("|---|---|---|")
    d = derived_metrics(rec)
    for key, label, desc, pct in RATIO_LABELS:
        if d.get(key) is None and key in ("engagement_rate_official", "profile_visit_rate", "follows_per_1k"):
            continue
        lines.append(f"| {label} | {fmt_ratio(d.get(key), pct)} | {desc} |")
    lines.append("")
    if thread_parts:
        lines.append(f"## 发出的正文（thread，共 {len(thread_parts) + 1} 条；指标只统计首条）")
        lines.append("")
        lines.append(quote_block("\n\n".join([rec.get("text") or ""] + [p.get("text") or "" for p in thread_parts])))
    else:
        lines.append("## 发出的正文")
        lines.append("")
        lines.append(quote_block(rec.get("text")))
    lines.append("")
    lines.append(f"## 回复（按赞排序，前 {top_n} 条；回复者 handle 已省略）")
    lines.append("")
    if replies:
        for i, r in enumerate(replies[:top_n], 1):
            text = (r.get("text") or "").replace("\n", " ").strip()
            lines.append(f"{i}. （{fmt_int(r.get('likes') or 0)} 赞）{text}")
        lines.append("")
        lines.append(f"共抓到 {len(replies)} 条回复。")
    else:
        lines.append("未抓到回复正文。用油猴脚本时：打开这条帖子的详情页、往下滚到回复区，再导出。")
        lines.append("复盘至少需要 10 条回复——抓不到就手动粘贴。")
    lines.append("")
    if quotes:
        lines.append(f"## 引用（按赞排序，前 {min(top_n, 10)} 条；引用者 handle 已省略）")
        lines.append("")
        for i, q in enumerate(quotes[:10], 1):
            text = (q.get("text") or "").replace("\n", " ").strip()
            lines.append(f"{i}. （{fmt_int(q.get('likes') or 0)} 赞）{text}")
        lines.append("")
    if final_text is not None:
        lines.append("## 预测时的定稿（posts/<id>/final.md）")
        lines.append("")
        lines.append(quote_block(final_text))
        lines.append("")
    files = rec.get("_files") or ([rec["_file"]] if rec.get("_file") else [])
    if files:
        lines.append("---")
        lines.append("")
        names = sorted({os.path.basename(str(f)) for f in files})
        lines.append("原始导出：" + "、".join(f"`{n}`" for n in names) + "（imports/ 不入库）")
        lines.append("")
    return "\n".join(lines)
