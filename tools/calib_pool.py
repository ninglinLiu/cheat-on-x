#!/usr/bin/env python3
"""calib_pool.py — read predictions/*.md and turn retros into numbers (cheat-on-x).

  baseline PRED_DIR [--last 10] [--json]
      per-form impression baseline = median of the last N retro'd samples of that form
      (excludes reconstructed / integrity-warning / exogenous samples). Used by cheatx-retro
      to update state.baseline_impressions.

  pool PRED_DIR [--formula-old EXPR] [--formula-new EXPR] [--rescores DIR] [--out FILE]
      calibration pool CSV for tools/rank_check.py and tools/score-curve.py:
      file, form, published_at, composite_old, composite_new, outcome_ratio, weight,
      impressions, baseline, center, ratio_to_center, log_score, flags, + one column per dimension.
      EXPR is a rubric formula over dimension codes, e.g.
      "(HK + RP + SV + RS + DW + FT + NF) / 7 * 2 - NR * 0.4"  (evaluated safely, no eval()).

Parsing contract = templates/prediction.template.md + templates/retro.template.md.
Exit: 0 ok · 2 bad input
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import operator
import re
import statistics
import sys
from pathlib import Path

_NUM = r"([\d][\d,]*(?:\.\d+)?)\s*([kKmM万]?)"
_MULT = {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6, "万": 1e4}


def num(s: str, unit: str = "") -> float:
    return float(s.replace(",", "")) * _MULT.get(unit, 1)


def header_fields(text: str) -> dict[str, str]:
    out = {}
    for line in text.split("\n## ", 1)[0].splitlines():
        m = re.match(r"\*\*(.+?)\*\*\s*[:：]\s*(.*)$", line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def split_sections(text: str) -> tuple[str, str]:
    """(prediction part = everything before '## 复盘', retro part)."""
    m = re.search(r"^## 复盘\s*$", text, re.M)
    if not m:
        return text, ""
    return text[: m.start()], text[m.end():]


def parse_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    hdr = header_fields(text)
    pred, retro = split_sections(text)
    rec: dict = {"file": str(path).replace("\\", "/"), "flags": []}
    rec["form"] = (hdr.get("Form") or "unknown").split(" ")[0].split("(")[0].strip() or "unknown"
    rec["published_at"] = hdr.get("Published at")
    if "Reconstructed retrospective" in text[:2000] or path.stem.endswith("_redo"):
        rec["flags"].append("reconstructed")
    # baseline value written in the header, e.g. "thread=n/a（…）→ all=420（…）" — take the last number
    bnums = re.findall(r"=\s*" + _NUM, hdr.get("Baseline", ""))
    rec["baseline"] = num(*bnums[-1]) if bnums else None
    # last score line / center / bucket probabilities in the prediction part
    scores = re.findall(r"\*\*分数[^*]*\*\*\s*[:：]\s*(.+)", pred)
    dims = {}
    if scores:
        for code, val in re.findall(r"\b([A-Z]{2,3})\s*=?\s*(\d)\b", scores[-1].split("→")[0]):
            dims[code] = int(val)
        cm = re.search(r"composite\s*=\s*\**\s*([\d.]+)", scores[-1])
        rec["composite_recorded"] = float(cm.group(1)) if cm else None
    rec["dims"] = dims
    centers = re.findall(r"\*\*中枢\*\*\s*[:：]\s*" + _NUM, pred)
    rec["center"] = num(*centers[-1]) if centers else None
    # probability per bucket from the LAST prediction section
    last_pred = re.split(r"^## 预测", pred, flags=re.M)[-1]
    probs = {}
    for name, p in re.findall(r"`(退步|持平|命中|小爆|大爆)`[^\n]*?→\s*(\d+(?:\.\d+)?)\s*%", last_pred):
        probs[name] = float(p) / 100
    rec["probs"] = probs
    if not retro.strip() or "（待填" in retro[:200]:
        return rec | {"retro": False}
    rec["retro"] = True
    im = re.search(r"曝光\s*[:：]\s*\**\s*" + _NUM, retro)
    rec["impressions"] = num(*im.groups()) if im else None
    bm = re.search(r"落在\s*`(退步|持平|命中|小爆|大爆)`", retro)
    rec["actual_bucket"] = bm.group(1) if bm else None
    if "exogenous_boost" in retro or re.search(r"外生冲击[:：]\s*(?!`?无)", retro):
        rec["flags"].append("exogenous")
    if "Integrity warning" in text or "⚠️" in hdr.get("Posted Text Check", ""):
        rec["flags"].append("integrity")
    if "early_retro: true" in retro or "early_snapshot" in retro:
        rec["flags"].append("early")
    return rec


def load_dir(pred_dir: Path) -> list[dict]:
    recs = []
    for p in sorted(pred_dir.glob("*.md")):
        r = parse_file(p)
        if r:
            recs.append(r)
    return recs


def usable(r: dict) -> bool:
    return (r.get("retro") and r.get("impressions") is not None
            and not {"reconstructed", "integrity", "exogenous"} & set(r["flags"]))


# ---------------------------------------------------------------- safe formula evaluation

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"max": max, "min": min}


def eval_formula(expr: str, dims: dict[str, int]) -> float | None:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in dims:
                raise KeyError(node.id)
            return dims[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"公式里不允许的写法：{ast.dump(node)[:60]}")
    expr = expr.replace("×", "*").replace("−", "-").replace("÷", "/")
    try:
        return float(ev(ast.parse(expr, mode="eval")))
    except KeyError:
        return None


# ---------------------------------------------------------------- commands

def cmd_baseline(a) -> int:
    recs = [r for r in load_dir(Path(a.pred_dir)) if usable(r)]
    recs.sort(key=lambda r: r.get("published_at") or "")
    by_form: dict[str, list[float]] = {}
    for r in recs:
        by_form.setdefault(r["form"], []).append(r["impressions"])
    out = {"all": statistics.median([r["impressions"] for r in recs][-a.last:]) if recs else None}
    counts = {"all": len(recs)}
    for f, vals in by_form.items():
        out[f] = statistics.median(vals[-a.last:]) if len(vals) >= 3 else None
        counts[f] = len(vals)
    if a.json:
        print(json.dumps({"baseline_impressions": out, "counts": counts, "last_n": a.last}, ensure_ascii=False, indent=2))
    else:
        for k, v in out.items():
            print(f"{k:8} {'—' if v is None else f'{v:,.0f}'}  (n={counts.get(k, 0)})")
    return 0


def load_rescores(d: Path) -> dict[str, dict[str, int]]:
    """cheatx-score-blind sidecars → {prediction stem: {dim: score}}.

    draft_path drafts/<stem>.md or posts/<stem>/final.md or .cheatx-cache/blind-input/<stem>.md
    maps to predictions/<stem>.md.
    """
    out: dict[str, dict[str, int]] = {}
    for f in sorted(d.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for res in data.get("results", []):
            if res.get("refusal") and res.get("refusal") != "non_blind_warning":
                continue
            p = Path(res.get("draft_path", ""))
            stem = p.parent.name if p.name == "final.md" else p.stem
            dims = {k: v["score"] for k, v in (res.get("dimensions") or {}).items() if isinstance(v, dict)}
            dims.update({k: v["score"] for k, v in (res.get("candidate_dimensions") or {}).items()
                         if isinstance(v, dict)})
            out.setdefault(stem, {}).update(dims)
    return out


def cmd_pool(a) -> int:
    recs = [r for r in load_dir(Path(a.pred_dir)) if r.get("retro")]
    if a.rescores:
        rs = load_rescores(Path(a.rescores))
        for r in recs:
            stem = Path(r["file"]).stem
            if stem in rs:
                r["dims"] = {**r["dims"], **rs[stem]}
                r["flags"].append("rescored")
    rows = []
    dim_codes = sorted({c for r in recs for c in r["dims"]})
    for r in recs:
        if r.get("impressions") is None:
            continue
        base = r.get("baseline")
        center = r.get("center")
        old = eval_formula(a.formula_old, r["dims"]) if a.formula_old else r.get("composite_recorded")
        new = eval_formula(a.formula_new, r["dims"]) if a.formula_new else None
        p = r["probs"].get(r.get("actual_bucket") or "", None)
        rows.append({
            "file": r["file"], "form": r["form"], "published_at": r.get("published_at"),
            "composite_old": None if old is None else round(max(0.0, old), 3),
            "composite_new": None if new is None else round(max(0.0, new), 3),
            "outcome_ratio": round(r["impressions"] / base, 4) if base else None,
            "weight": 0.5 if "early" in r["flags"] else 1.0,
            "impressions": r["impressions"], "baseline": base, "center": center,
            "ratio_to_center": round(r["impressions"] / center, 4) if center else None,
            "log_score": round(math.log(p), 4) if p else None,
            "flags": "|".join(r["flags"]),
            **{f"dim_{c}": r["dims"].get(c) for c in dim_codes},
        })
    excluded = [x for x in rows if {"reconstructed", "integrity", "exogenous"} & set(x["flags"].split("|"))]
    rows_out = rows if a.include_excluded else [x for x in rows if x not in excluded]
    fields = ["file", "form", "published_at", "composite_old", "composite_new", "outcome_ratio", "weight",
              "impressions", "baseline", "center", "ratio_to_center", "log_score", "flags"] + [f"dim_{c}" for c in dim_codes]
    out = open(a.out, "w", encoding="utf-8", newline="") if a.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=fields)
    w.writeheader()
    for x in rows_out:
        w.writerow({k: ("" if v is None else v) for k, v in x.items()})
    if a.out:
        out.close()
    missing_new = sum(1 for x in rows_out if a.formula_new and x["composite_new"] is None)
    print(f"[calib_pool] {len(rows_out)} 条进池，排除 {len(excluded)} 条（reconstructed / integrity / exogenous）"
          + (f"；{missing_new} 条缺新公式需要的维度分，需回补" if missing_new else ""), file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("baseline")
    s.add_argument("pred_dir")
    s.add_argument("--last", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("pool")
    s.add_argument("pred_dir")
    s.add_argument("--formula-old")
    s.add_argument("--formula-new")
    s.add_argument("--out")
    s.add_argument("--rescores", help="目录：cheatx-score-blind 写的 sidecar JSON（回补 / 重打的维度分覆盖预测文件里的）")
    s.add_argument("--include-excluded", action="store_true")
    a = p.parse_args(argv)
    if not Path(a.pred_dir).is_dir():
        print(f"❌ 不是目录：{a.pred_dir}", file=sys.stderr)
        return 2
    try:
        return cmd_baseline(a) if a.cmd == "baseline" else cmd_pool(a)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
