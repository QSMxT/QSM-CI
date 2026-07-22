#!/usr/bin/env python3
"""Aggregate sweep results into a baseline-vs-best table (optimising xSIM).

Reads every results/sweep_*.json (round 1) and results/sweep_refine_*.json (round 2), and for each
algorithm reports the no-override baseline xSIM, the best grid point, and the winning override.

  python scripts/sweep_report.py [--dir results]
"""
from __future__ import annotations

import argparse
import glob
import json
import os


def load(path) -> list:
    try:
        return json.load(open(path))
    except Exception:
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results")
    args = ap.parse_args()

    by_slug: dict[str, list] = {}
    for path in sorted(glob.glob(os.path.join(args.dir, "sweep_*.json"))):
        for r in load(path):
            if r.get("status") == "ok" and r.get("xsim") is not None:
                by_slug.setdefault(r["slug"], []).append(r)

    print(f"{'algorithm':<14} {'baseline':>9} {'best':>9} {'Δ':>8}   best override")
    print("-" * 72)
    rows = []
    for slug in sorted(by_slug):
        runs = by_slug[slug]
        base = next((r["xsim"] for r in runs if not r["override"]), None)
        best = max(runs, key=lambda r: r["xsim"])
        rows.append((slug, base, best))
    # sort by improvement, biggest first
    def delta(row):
        _, base, best = row
        return (best["xsim"] - base) if base is not None else -1
    for slug, base, best in sorted(rows, key=delta, reverse=True):
        ov = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                       for k, v in best["override"].items()) or "(default is best)"
        b = f"{base:.4f}" if base is not None else "   n/a"
        d = f"{best['xsim'] - base:+.4f}" if base is not None else "   n/a"
        print(f"{slug:<14} {b:>9} {best['xsim']:>9.4f} {d:>8}   {ov}")


if __name__ == "__main__":
    main()
