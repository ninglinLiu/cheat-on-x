#!/usr/bin/env python3
"""rank_check.py — deterministic Step 3 of the cheat-on-x bump protocol.

Input CSV columns (header required):
  file, form, composite_old, composite_new, outcome_ratio[, weight]
    outcome_ratio = actual impressions / the Baseline recorded in that prediction's header
    weight        = optional sample weight (early retro 0.5, default 1)

Checks (defaults match shared-references/bump-validation-protocol.md):
  1. rho_new >= rho_old + MIN_GAIN (0.05)
  2. rho_new >= MIN_RHO (0.25)
  3. bootstrap: share of resamples where rho_new > rho_old >= THRESHOLD (0.80)
  4. per form with n >= 5: rho_new must not fall more than MAX_FORM_DROP (0.10) below rho_old

Usage:  python tools/rank_check.py .cheatx-cache/bump-pool.csv [--iters 1000] [--seed 42] [--json]
Exit:   0 PASS · 1 FAIL · 2 bad input
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

MIN_GAIN = 0.05
MIN_RHO = 0.25
THRESHOLD = 0.80
MAX_FORM_DROP = 0.10
MIN_FORM_N = 5


def ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share the mean rank), 1-based."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def weighted_pearson(x: list[float], y: list[float], w: list[float]) -> float | None:
    sw = sum(w)
    if sw <= 0 or len(x) < 3:
        return None
    mx = sum(wi * xi for wi, xi in zip(w, x)) / sw
    my = sum(wi * yi for wi, yi in zip(w, y)) / sw
    cov = sum(wi * (xi - mx) * (yi - my) for wi, xi, yi in zip(w, x, y))
    vx = sum(wi * (xi - mx) ** 2 for wi, xi in zip(w, x))
    vy = sum(wi * (yi - my) ** 2 for wi, yi in zip(w, y))
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def spearman(x: list[float], y: list[float], w: list[float] | None = None) -> float | None:
    w = w or [1.0] * len(x)
    return weighted_pearson(ranks(x), ranks(y), w)


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    need = {"file", "form", "composite_old", "composite_new", "outcome_ratio"}
    if not rows or not need <= set(rows[0]):
        raise ValueError(f"CSV 需要列：{', '.join(sorted(need))}（weight 可选）")
    out = []
    for r in rows:
        try:
            out.append({"file": r["file"], "form": (r.get("form") or "").strip() or "unknown",
                        "old": float(r["composite_old"]), "new": float(r["composite_new"]),
                        "y": float(r["outcome_ratio"]), "w": float(r.get("weight") or 1)})
        except ValueError as e:
            raise ValueError(f"行 {r.get('file')!r} 数值无效：{e}") from e
    return out


def check(rows: list[dict], iters: int = 1000, seed: int = 42) -> dict:
    x_old = [r["old"] for r in rows]
    x_new = [r["new"] for r in rows]
    y = [r["y"] for r in rows]
    w = [r["w"] for r in rows]
    rho_old = spearman(x_old, y, w)
    rho_new = spearman(x_new, y, w)
    rng = random.Random(seed)
    n = len(rows)
    wins = valid = 0
    for _ in range(iters):
        idx = rng.choices(range(n), weights=w, k=n)
        ro = spearman([x_old[i] for i in idx], [y[i] for i in idx])
        rn = spearman([x_new[i] for i in idx], [y[i] for i in idx])
        if ro is None or rn is None:
            continue
        valid += 1
        wins += rn > ro
    stability = wins / valid if valid else None
    forms = {}
    for f in sorted({r["form"] for r in rows}):
        sub = [r for r in rows if r["form"] == f]
        if len(sub) < MIN_FORM_N:
            forms[f] = {"n": len(sub), "checked": False}
            continue
        fo = spearman([r["old"] for r in sub], [r["y"] for r in sub], [r["w"] for r in sub])
        fn = spearman([r["new"] for r in sub], [r["y"] for r in sub], [r["w"] for r in sub])
        ok = fo is None or fn is None or fn >= fo - MAX_FORM_DROP
        forms[f] = {"n": len(sub), "checked": True, "rho_old": fo, "rho_new": fn, "ok": ok}
    criteria = {
        "gain": rho_old is not None and rho_new is not None and rho_new >= rho_old + MIN_GAIN,
        "min_rho": rho_new is not None and rho_new >= MIN_RHO,
        "stability": stability is not None and stability >= THRESHOLD,
        "no_form_regression": all(v.get("ok", True) for v in forms.values()),
    }
    return {"n": n, "rho_old": rho_old, "rho_new": rho_new, "bootstrap_iters": valid,
            "stability": stability, "forms": forms, "criteria": criteria,
            "verdict": "PASS" if all(criteria.values()) else "FAIL",
            "thresholds": {"min_gain": MIN_GAIN, "min_rho": MIN_RHO, "threshold": THRESHOLD,
                           "max_form_drop": MAX_FORM_DROP, "min_form_n": MIN_FORM_N}}


def fmt(v) -> str:
    return "—" if v is None else f"{v:.3f}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--iters", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        rows = load(Path(a.csv))
    except (OSError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if len(rows) < 5:
        print(f"❌ 样本只有 {len(rows)} 条，至少 5 条才有意义", file=sys.stderr)
        return 2
    res = check(rows, a.iters, a.seed)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        c = res["criteria"]
        print(f"样本 {res['n']} 条")
        print(f"Spearman ρ  旧 {fmt(res['rho_old'])} → 新 {fmt(res['rho_new'])}"
              f"   [{'✓' if c['gain'] else '✗'} 提升 ≥ {MIN_GAIN}] [{'✓' if c['min_rho'] else '✗'} 新 ρ ≥ {MIN_RHO}]")
        print(f"自助重采样 {res['bootstrap_iters']} 次：新公式更好的比例 {fmt(res['stability'])}"
              f"   [{'✓' if c['stability'] else '✗'} ≥ {THRESHOLD}]")
        for f, v in res["forms"].items():
            if v["checked"]:
                print(f"  形态 {f}（n={v['n']}）：ρ {fmt(v['rho_old'])} → {fmt(v['rho_new'])} {'✓' if v['ok'] else '✗ 退步超过 ' + str(MAX_FORM_DROP)}")
            else:
                print(f"  形态 {f}（n={v['n']}）：样本 < {MIN_FORM_N}，不单独检验")
        print(f"\n结论：{res['verdict']}")
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
