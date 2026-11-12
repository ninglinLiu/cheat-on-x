"""Column-name aliases → canonical field names.

Every CSV source (the cheatx userscript, X Analytics exports, third-party userscripts or
browser extensions) names its columns differently. Matching is done on a normalized key:
lowercase, with spaces / underscores / hyphens / dots removed.

To support a new export format, add its column names here (or pass `--map col=field`
on the command line). Run `python import_csv.py inspect <file.csv>` to see how a file maps.
"""
from __future__ import annotations

import re

# canonical field -> aliases (any spelling; normalized at import time)
ALIASES: dict[str, list[str]] = {
    "post_id": ["post_id", "post id", "tweet_id", "tweet id", "status_id", "rest_id", "id",
                "帖子id", "推文id", "帖子 id", "推文 id"],
    "url": ["url", "post link", "post url", "tweet permalink", "permalink", "link",
            "链接", "帖子链接", "推文链接"],
    "author": ["author", "username", "screen_name", "screen name", "handle", "user",
               "作者", "用户名"],
    "created_at": ["created_at", "created at", "date", "time", "post date", "created",
                   "发布时间", "时间", "日期"],
    "captured_at": ["captured_at", "captured at", "snapshot_at", "exported_at", "抓取时间", "导出时间"],
    "text": ["text", "post text", "tweet text", "full_text", "content",
             "正文", "内容", "帖子内容", "推文内容", "帖子文本"],
    "impressions": ["impressions", "views", "view_count", "view count", "impression_count",
                    "展示次数", "展示量", "曝光", "曝光次数", "曝光量", "浏览", "浏览量",
                    "查看次数", "观看次数"],
    "likes": ["likes", "like_count", "favorite_count", "favorites", "favs",
              "喜欢", "喜欢次数", "点赞", "点赞数", "赞"],
    "reposts": ["reposts", "retweets", "retweet_count", "repost_count",
                "转帖", "转推", "转发", "转发数"],
    "quotes": ["quotes", "quote_count", "quote tweets", "引用", "引用次数", "引用数"],
    "replies": ["replies", "reply_count", "回复", "回复数", "回复次数"],
    "bookmarks": ["bookmarks", "bookmark_count", "书签", "收藏", "收藏数"],
    "engagements": ["engagements", "engagement", "互动", "互动次数", "互动量"],
    "profile_visits": ["profile visits", "profile clicks", "user profile clicks",
                       "user_profile_clicks", "个人资料访问", "个人资料访问次数",
                       "个人资料点击", "主页访问"],
    "new_follows": ["new follows", "new followers", "follows", "新关注者", "新增关注",
                    "新关注", "关注"],
    "link_clicks": ["url clicks", "link clicks", "url_link_clicks", "链接点击", "链接点击次数"],
    "detail_expands": ["detail expands", "详细信息展开", "详情展开", "展开详情"],
    "media_views": ["media views", "媒体浏览", "媒体观看", "媒体浏览量"],
    "shares": ["shares", "share", "分享", "分享次数"],
    # Fields below are written by the cheatx userscript under their canonical names.
    "has_link": ["has_link"],
    "media": ["media", "media_types"],
    "lang": ["lang", "language", "语言"],
    "in_reply_to_id": ["in_reply_to_id", "in_reply_to_status_id"],
    "in_reply_to_user": ["in_reply_to_user", "in_reply_to_screen_name"],
    "conversation_id": ["conversation_id"],
    "quoted_id": ["quoted_id", "quoted_status_id"],
    "is_note_tweet": ["is_note_tweet", "is_long"],
    "is_article": ["is_article"],
    "form": ["form", "形态"],
    "source": ["source", "来源"],
}

METRIC_FIELDS = [
    "impressions", "likes", "reposts", "quotes", "replies", "bookmarks", "engagements",
    "profile_visits", "new_follows", "link_clicks", "detail_expands", "media_views", "shares",
]

CANONICAL_FIELDS = list(ALIASES.keys())

_NORM_RE = re.compile(r"[\s_\-./()（）:：]+")


def norm_key(name: str) -> str:
    return _NORM_RE.sub("", name.strip().lstrip("﻿").lower())


ALIAS_INDEX: dict[str, str] = {}
for _field, _names in ALIASES.items():
    for _n in [_field] + _names:
        ALIAS_INDEX.setdefault(norm_key(_n), _field)


def map_columns(headers: list[str], overrides: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Return ({source_header: canonical_field}, [unmapped headers]).

    `overrides` maps a source header (any spelling) to a canonical field and wins over
    the alias table. A canonical field is assigned to at most one column (first wins).
    """
    overrides = {norm_key(k): v for k, v in (overrides or {}).items()}
    for v in overrides.values():
        if v not in CANONICAL_FIELDS:
            raise ValueError(f"--map target '{v}' is not a canonical field; valid: {', '.join(CANONICAL_FIELDS)}")
    mapping: dict[str, str] = {}
    used: set[str] = set()
    # pass 1: explicit overrides win
    for h in headers:
        field = overrides.get(norm_key(h))
        if field and field not in used:
            mapping[h] = field
            used.add(field)
    # pass 2: alias table
    for h in headers:
        if h in mapping:
            continue
        field = ALIAS_INDEX.get(norm_key(h))
        if field and field not in used:
            mapping[h] = field
            used.add(field)
    unmapped = [h for h in headers if h not in mapping]
    return mapping, unmapped
