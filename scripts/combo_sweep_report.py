#!/usr/bin/env python3
"""Read a combination sweep and answer: does each dipole's ISOLATED-tuned value stay optimal once
it's chained behind a specific BFR?

For every (bfr -> dipole) cell it prints the xSIM at the dipole's isolated-tuned override, the best
grid point found in-combination, the gap between them, and whether the winning override differs from
the isolated one. A cell flagged "MOVED" is direct evidence that per-combination tuning would help —
the cells that move are exactly the ones worth a proper joint sweep (and worth storing separately in
tuning/combinations.yml).

  python scripts/combo_sweep_report.py [--in results/combo_sweep.json] [--min-delta 0.002]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict


def ov_str(ov: dict) -> str:
    return ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                     for k, v in ov.items()) or "(default)"


def key(ov: dict) -> tuple:
    return tuple(sorted((k, f"{v:g}" if isinstance(v, float) else str(v)) for k, v in ov.items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path", default="results/combo_sweep.json")
    ap.add_argument("--min-delta", type=float, default=0.002,
                    help="xSIM gain over the isolated-tuned point needed to flag a cell as MOVED")
    args = ap.parse_args()

    runs = [r for r in json.load(open(args.path)) if r.get("status") == "ok" and r.get("xsim") is not None]
    if not runs:
        raise SystemExit(f"no scored runs in {args.path}")

    # group by (bfr, bfr_tag, dipole)
    cells: dict[tuple, list] = defaultdict(list)
    for r in runs:
        cells[(r["bfr"], r.get("bfr_tag", "default"), r["dipole"])].append(r)

    print(f"{'bfr':<14} {'dipole':<12} {'iso-tuned':>9} {'best':>9} {'Δ':>8}   best override  [iso override]")
    print("-" * 96)
    moved, checked = 0, 0
    dipole_moves: dict[str, int] = defaultdict(int)
    dipole_seen: dict[str, int] = defaultdict(int)

    for (bfr, bfr_tag, dipole) in sorted(cells):
        rs = cells[(bfr, bfr_tag, dipole)]
        iso_ov = rs[0].get("isolated_tuned") or {}
        best = max(rs, key=lambda r: r["xsim"])
        iso_run = next((r for r in rs if key(r["override"]) == key(iso_ov)), None) if iso_ov else None
        # fall back to the method's built-in default point when no isolated-tuned value is declared
        base_run = iso_run or next((r for r in rs if not r["override"]), None)
        base = base_run["xsim"] if base_run else None
        d = best["xsim"] - base if base is not None else None
        tag = bfr if bfr_tag == "default" else f"{bfr}[{bfr_tag}]"
        dipole_seen[dipole] += 1
        flag = ""
        if base is not None:
            checked += 1
            if d >= args.min_delta and key(best["override"]) != key(base_run["override"]):
                flag = "  <- MOVED"; moved += 1; dipole_moves[dipole] += 1
        bs = f"{base:.4f}" if base is not None else "   n/a"
        ds = f"{d:+.4f}" if d is not None else "   n/a"
        print(f"{tag:<14} {dipole:<12} {bs:>9} {best['xsim']:>9.4f} {ds:>8}   "
              f"{ov_str(best['override'])}  [{ov_str(iso_ov)}]{flag}")

    print("-" * 96)
    print(f"{moved}/{checked} cells improved by >= {args.min_delta} xSIM when tuned in combination.")
    if moved:
        print("dipoles whose optimum shifts most (cells moved / cells seen):")
        for dip in sorted(dipole_moves, key=dipole_moves.get, reverse=True):
            print(f"  {dip:<12} {dipole_moves[dip]}/{dipole_seen[dip]}")
        print("\n=> per-combination tuning is justified for the MOVED cells; store their winning "
              "overrides in tuning/combinations.yml keyed by (bfr, dipole).")
    else:
        print("=> isolated-tuned values hold up in combination; combination tuning is NOT justified "
              "on this dataset. (Re-check on data/sim/scoring before concluding.)")


if __name__ == "__main__":
    main()
