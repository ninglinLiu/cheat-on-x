#!/usr/bin/env python3
"""cheat-on-x SessionStart report (stdlib only, Python 3.8+).

Prints a short status block into Claude's context at the start of every session:
due retros, today's posts vs target, queue color, top candidates, confidence, warnings.
Read-only: never writes anything. Silent if the directory is not a cheat-on-x project.

Usage: python session_start.py [PROJECT_DIR]      (called by session-start.sh)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LATEST_SCHEMA = "x1.0"   # keep in sync with migrations/registry.md
LONGFORM = ("long", "article")
TOP_LEVEL = ("single", "thread", "long", "article", "quote")


def parse_iso(s):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(:\d{2}(?:\.\d+)?)?(.*)$", s)
    if m and not m.group(3):          # 2026-11-12T21:03+08:00 → add seconds for py<3.11
        s = f"{m.group(1)}T{m.group(2)}:00{m.group(4)}"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()


def confidence(n: int) -> str:
    if n <= 0:
        return "🔴 极低（纯纪律训练）"
    if n <= 4:
        return "🟠 低（中枢 ±60%）"
    if n <= 14:
        return "🟡 偏低（中枢 ±40%）"
    if n <= 39:
        return "🟢 中（中枢 ±25%）"
    if n <= 99:
        return "🟢 较高（中枢 ±15%）"
    return "🔵 高（中枢 ±10%）"


def header_field(path: Path, key: str):
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                break
            m = re.match(r"\*\*" + re.escape(key) + r"\*\*\s*[:：]\s*(.*)$", line.strip())
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return None


def top_candidates(path: Path, now: datetime, n: int = 3):
    if not path.is_file():
        return []
    items, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (?:\[(\w+)\]\s*)?(.+)$", line)
        if m:
            cur = {"tier": m.group(1), "title": m.group(2).strip(), "score": None, "expired": False}
            items.append(cur)
            continue
        if cur is None:
            continue
        cm = re.search(r"composite[^:：]*[:：]\s*([\d.]+)", line)
        if cm:
            try:
                cur["score"] = float(cm.group(1))
            except ValueError:
                pass
        em = re.search(r"expires_at\**\s*[:：]\s*(\S+)", line)
        if em:
            exp = parse_iso(em.group(1))
            if exp and exp < now:
                cur["expired"] = True
    live = [c for c in items if c["tier"] not in ("skip", "done") and not c["expired"]]
    live.sort(key=lambda c: (c["score"] is None, -(c["score"] or 0)))
    return live[:n]


def main(argv) -> int:
    project = Path(argv[1] if len(argv) > 1 else ".")
    state_path = project / ".cheatx-state.json"
    if not state_path.is_file():
        return 0
    try:
        st = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("[cheat-on-x] ⚠️ .cheatx-state.json 读不了或不是合法 JSON——说 \"X 状态\" 检查。")
        return 0
    now = datetime.now(timezone.utc).astimezone()
    today = now.date()
    lines, warns = [], []

    # due retros
    w_short = st.get("retro_window_hours", 48)
    w_long = st.get("retro_window_hours_longform", 168)
    due, soon, earliest = 0, 0, None
    for item in st.get("pending_retros", []):
        if isinstance(item, str):
            item = {"file": item}
        due_at = parse_iso(item.get("due_at"))
        if due_at is None:
            pub = parse_iso(item.get("published_at")) or parse_iso(header_field(project / item["file"], "Published at"))
            if pub:
                due_at = pub + timedelta(hours=w_long if item.get("form") in LONGFORM else w_short)
        if due_at is None:
            continue
        if due_at <= now:
            due += 1
            earliest = due_at if earliest is None or due_at < earliest else earliest
        elif due_at <= now + timedelta(hours=24):
            soon += 1
    if due:
        lines.append(f"⏰ 到期待复盘 {due} 条（最早 {earliest:%m-%d %H:%M}）"
                     + (f"，24 小时内还有 {soon} 条" if soon else "")
                     + " → x.com 导出 CSV 后说 \"复盘到期的 imports/<文件>.csv\"")
    else:
        lines.append(f"⏰ 到期待复盘：无" + (f"（24 小时内 {soon} 条到期）" if soon else ""))

    # today's posts
    target = st.get("target_posts_per_day")
    pubs = [p for p in st.get("recent_publishes", []) if isinstance(p, dict)]
    today_main = sum(1 for p in pubs if (parse_iso(p.get("at")) or now).date() == today and p.get("form", "single") in TOP_LEVEL)
    today_reply = sum(1 for p in pubs if (parse_iso(p.get("at")) or now).date() == today and p.get("form") == "reply")
    last = max((parse_iso(p.get("at")) for p in pubs if parse_iso(p.get("at"))), default=None)
    since = f" · 距上一条 {int((now - last).total_seconds() // 60)} 分钟" if last else ""
    lines.append(f"📤 今天主帖 {today_main}" + (f" / {target}" if target else "") + (f" · 回复 {today_reply}" if today_reply else "") + since)

    # queue
    q = [x for x in st.get("queue", []) if isinstance(x, dict)]
    if target:
        days = len(q) / target
        color = "🔴" if days < 0.5 else "🟠" if days < 1 else "🟢" if days <= 3 else "🔵"
        lines.append(f"📦 队列 {len(q)} 条 ≈ {days:.1f} 天 {color}")
        if color == "🔴":
            warns.append("🚨 队列见底：今天的条数还没着落——说 \"推荐今天发什么\"，只推稳分 top 1")
        if color == "🔵":
            warns.append("📦 队列积压：先发存货，别再写新的")
    else:
        lines.append(f"📦 队列 {len(q)} 条（灵活节奏，不警戒）")
    oldest = min((parse_iso(x.get("queued_at")) for x in q if parse_iso(x.get("queued_at"))), default=None)
    if oldest and now - oldest > timedelta(days=3):
        warns.append(f"⌛ 队列里最久的一条已排了 {(now - oldest).days} 天——热点类可能已经过期")

    # candidates
    tops = top_candidates(project / "candidates.md", now)
    if tops:
        lines.append("🎯 候选 top：" + " / ".join(c["title"][:24] + (f"（{c['score']:.1f}）" if c["score"] else "") for c in tops))
    else:
        lines.append("🎯 候选池空——说 \"找选题\" 或 \"抓 X 热点\"")

    # calibration
    n = int(st.get("calibration_samples", 0) or 0)
    lines.append(f"📈 rubric {st.get('rubric_version', 'v0')} · 校准样本 {n} · confidence {confidence(n)}")

    # warnings
    if st.get("edition") != "x":
        warns.append("⚠️ state 没有 edition=x 标记——可能不是 cheat-on-x 的状态文件")
    sv = st.get("schema_version", "unknown")
    if sv != LATEST_SCHEMA:
        warns.append(f"⚠️ schema 不一致：state={sv}，当前版本期望 {LATEST_SCHEMA}——建议 /cheatx-migrate（不阻塞）")
    if st.get("last_prediction_self_scored"):
        t = parse_iso(st.get("last_self_scored_at"))
        d = (now - t).days if t else "?"
        warns.append(f"⚠️ 上次预测没走盲打 sub-agent（{d} 天前）——下次正常预测即可清除")
    ips = st.get("in_progress_session")
    if isinstance(ips, dict):
        started = parse_iso(ips.get("started_at"))
        if started and now - started > timedelta(hours=2):
            warns.append(f"⚠️ 有一个中断的 {ips.get('type', '流程')}（{started:%m-%d %H:%M} 开始）——继续还是清掉？")
    if not st.get("hooks_installed"):
        warns.append("⚠️ 预测锁 hook 没装——盲预测保护是君子协定")
    if st.get("benchmark_status") == "pending":
        warns.append("🎯 还没导入对标账号——/cheatx-learn-from")

    print("")
    print("[cheat-on-x / 开场状态]")
    for line in lines:
        print(line)
    for w in warns[:4]:
        print(w)
    print("（不要主动开始任何动作——等用户决定。说 \"X 状态\" 看完整看板。）")
    print("")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to a legacy codepage
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv))
