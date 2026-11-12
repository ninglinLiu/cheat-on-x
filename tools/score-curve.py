#!/usr/bin/env python3
"""
score-curve.py — is your prediction accuracy converging? (cheat-on-x)

Reads predictions/*.md (via calib_pool.py's parser), and for every retro'd sample computes:
  - |log2(actual / predicted center)|   → 0 = spot on, 1 = off by 2×, 2 = off by 4×
  - log score = ln(probability you gave the bucket that actually happened) → closer to 0 is better
then plots rolling means over time (by published date). A calibrating rubric shows both lines
moving toward 0; a drifting one shows them widening.

Excluded: reconstructed / integrity-warning / exogenous-boost samples.

Usage:
    python tools/score-curve.py [--predictions DIR] [--out PATH] [--window N]
Defaults: --predictions ./predictions  --out score-curve.png  --window 10
Dependencies: stdlib; matplotlib optional (without it a CSV table is printed instead).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calib_pool import load_dir, usable  # noqa: E402


def rolling(values: list[float | None], window: int) -> list[float | None]:
    out = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--predictions", default="predictions")
    p.add_argument("--out", default="score-curve.png")
    p.add_argument("--window", type=int, default=10)
    a = p.parse_args(argv)
    pred_dir = Path(a.predictions)
    if not pred_dir.is_dir():
        print(f"❌ 不是目录：{pred_dir}", file=sys.stderr)
        return 2
    recs = [r for r in load_dir(pred_dir) if usable(r) and r.get("center")]
    recs.sort(key=lambda r: r.get("published_at") or Path(r["file"]).name)
    if not recs:
        print("还没有可用的复盘样本。", file=sys.stderr)
        return 0
    err = [abs(math.log2(r["impressions"] / r["center"])) if r["impressions"] > 0 else None for r in recs]
    logs = []
    for r in recs:
        prob = r["probs"].get(r.get("actual_bucket") or "")
        logs.append(math.log(prob) if prob else None)
    err_roll = rolling(err, a.window)
    log_roll = rolling(logs, a.window)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("n,file,abs_log2_error,log_score,rolling_abs_log2_error,rolling_log_score")
        for i, r in enumerate(recs, 1):
            def f(v):
                return "" if v is None else f"{v:.3f}"
            print(f"{i},{Path(r['file']).name},{f(err[i-1])},{f(logs[i-1])},{f(err_roll[i-1])},{f(log_roll[i-1])}")
        print("（装 matplotlib 可以出图：pip install matplotlib）", file=sys.stderr)
        return 0

    xs = list(range(1, len(recs) + 1))
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    # English labels: matplotlib's default fonts have no CJK glyphs
    ax1.scatter(xs, [e if e is not None else float("nan") for e in err], s=12, alpha=0.35,
                label="|log2(actual / center)|")
    ax1.plot(xs, [e if e is not None else float("nan") for e in err_roll], linewidth=2,
             label=f"rolling mean ({a.window})")
    ax1.set_xlabel("calibration sample (by publish time)")
    ax1.set_ylabel("center error (0 = exact, 1 = off by 2x)")
    ax2 = ax1.twinx()
    ax2.plot(xs, [v if v is not None else float("nan") for v in log_roll], linestyle="--", linewidth=1.5,
             color="tab:red", label="rolling log score")
    ax2.set_ylabel("log score (closer to 0 is better)")
    lines = ax1.get_legend_handles_labels()
    lines2 = ax2.get_legend_handles_labels()
    ax1.legend(lines[0] + lines2[0], lines[1] + lines2[1], loc="upper right", fontsize=8)
    ax1.set_title("cheat-on-x: is the rubric converging?")
    fig.tight_layout()
    fig.savefig(a.out, dpi=150)
    print(f"✅ 写入 {a.out}（{len(recs)} 条样本）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
