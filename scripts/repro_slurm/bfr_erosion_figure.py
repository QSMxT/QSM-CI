#!/usr/bin/env python3
"""Dumbbell chart: per-BFR inter-scanner reproducibility, un-eroded vs 1-eroded input mask.
Shows erosion 'levelling the field' — the boundary-sensitive BFRs (lbv/harperella/vsharp) collapse
toward the already-robust ones (vsharp-sti/resharp), which barely move. (The original figure
also showed msmv, since removed from QSM-CI and so absent from any repro.json regenerated after
2026-09.)

Usage: bfr_erosion_figure.py <eroded repro.json> <un-eroded repro.json> <out.png>
"""
import json, sys, statistics as st
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ero_p, non_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
# repro.json used to carry the MEDIAN under the `_mean_` name; it now carries both separately.
# This figure always plotted the median, so it follows the value rather than the old key name.
KEY = "inter_scanner_median_abs_slope_dev"


def bfr_meds(path):
    p = json.load(open(path))["pipelines"]
    g = {}
    for pid, node in p.items():
        parts = pid.split("+")
        if len(parts) != 3 or node.get(KEY) is None:
            continue
        g.setdefault(parts[1], []).append(node[KEY])
    return {b: st.median(v) for b, v in g.items()}


non, ero = bfr_meds(non_p), bfr_meds(ero_p)
bfrs = sorted(set(non) & set(ero), key=lambda b: ero[b])   # best (lowest) eroded at bottom
y = np.arange(len(bfrs))

fig, ax = plt.subplots(figsize=(9, 6.5))
for i, b in enumerate(bfrs):
    n, e = non[b], ero[b]
    improved = e < n
    ax.plot([n, e], [i, i], "-", color="#c0392b" if improved else "#7f8c8d",
            lw=2, zorder=1, alpha=0.8)
    ax.scatter(n, i, s=55, color="#95a5a6", zorder=2, label="un-eroded" if i == 0 else None)
    ax.scatter(e, i, s=70, color="#c0392b", zorder=3, label="1-eroded" if i == 0 else None)
    d = e - n
    ax.annotate(f"{d:+.3f}", (min(n, e), i), textcoords="offset points", xytext=(-6, 0),
                ha="right", va="center", fontsize=7.5, color="#c0392b" if improved else "#7f8c8d")

ax.set_yticks(y)
ax.set_yticklabels(bfrs, fontsize=9)
ax.set_xlabel("inter-scanner |a-1|   (lower = more reproducible)")
ax.set_title("Effect of 1-voxel mask erosion on BFR reproducibility\n"
             "erosion rescues the boundary-sensitive BFRs; the robust ones barely move", fontsize=11)
ax.grid(axis="x", alpha=0.3)
ax.legend(loc="lower right", frameon=True)
# annotate the leveling: between-BFR spread before/after
sn = max(non.values()) - min(non.values()); se = max(ero.values()) - min(ero.values())
ax.text(0.30, 0.955, f"between-BFR spread  {sn:.3f} → {se:.3f}  ({100*(se-sn)/sn:+.0f}%)",
        transform=ax.transAxes, ha="left", va="top", fontsize=9.5, style="italic", color="#2c3e50",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f4f6f7", ec="#bdc3c7"))
plt.tight_layout()
plt.savefig(out, dpi=140)
print("wrote", out, "|", len(bfrs), "BFRs")
