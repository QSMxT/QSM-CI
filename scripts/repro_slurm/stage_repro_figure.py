#!/usr/bin/env python3
"""Decompose harmonization reproducibility by pipeline stage (field-mapping / BFR / dipole).

Usage: stage_repro_figure.py repro.json [repro_synthstrip.json] out.png
Reads repro.json (pipelines -> {test_retest,inter_scanner,inter_protocol}_median_abs_slope_dev), parses
each 3-stage composed pipeline id `fm+bfr+dipole`, and plots reproducibility grouped by each stage,
plus a one-way variance-explained (eta^2) per stage per metric.
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

args = [a for a in sys.argv[1:]]
out = args.pop() if args and args[-1].endswith(".png") else "stage_repro.png"
paths = args or ["results/repro.json"]

# repro.json used to carry the MEDIAN under the `_mean_` name; it now carries both separately,
# and `_mean_` is a genuine mean. These figures were always plotting the median, so they follow
# the value, not the old key name.
METRICS = [("inter_scanner_median_abs_slope_dev", "inter-scanner"),
           ("test_retest_median_abs_slope_dev", "test-retest"),
           ("inter_protocol_median_abs_slope_dev", "inter-protocol")]
STAGES = ["field-mapping", "bfr", "dipole"]


def parse(pid):
    parts = pid.split("+")
    if len(parts) == 3:
        return dict(zip(STAGES, parts))
    return None


def rows_from(path):
    pipes = json.load(open(path))["pipelines"]
    rows = []
    for pid, node in pipes.items():
        st = parse(pid)
        if not st:
            continue
        st = {**st, "pid": pid}
        for key, _ in METRICS:
            st[key] = node.get(key)
        rows.append(st)
    return rows


def eta2(rows, stage, metric):
    """one-way variance explained by `stage` for `metric` (SS_between / SS_total)."""
    vals = [(r[stage], r[metric]) for r in rows if r.get(metric) is not None]
    if len(vals) < 4:
        return float("nan")
    grand = np.mean([v for _, v in vals])
    sst = sum((v - grand) ** 2 for _, v in vals)
    groups = {}
    for g, v in vals:
        groups.setdefault(g, []).append(v)
    ssb = sum(len(vs) * (np.mean(vs) - grand) ** 2 for vs in groups.values())
    return ssb / sst if sst else float("nan")


# primary label set = HD-BET (first path); baseline (2nd path) drawn as reference medians if given
main = rows_from(paths[0])
print(f"{len(main)} three-stage pipelines from {paths[0]}")
METRIC = METRICS[0][0]

fig, axes = plt.subplots(1, 3, figsize=(19, 6.5))
for ax, stage in zip(axes, STAGES):
    groups = {}
    for r in main:
        if r.get(METRIC) is not None:
            groups.setdefault(r[stage], []).append(r[METRIC])
    order = sorted(groups, key=lambda k: np.median(groups[k]))
    ax.boxplot([groups[k] for k in order], vert=False, labels=order, showfliers=False,
               medianprops=dict(color="C3"))
    e = eta2(main, stage, METRIC)
    ax.set_title(f"{stage}   ({len(order)} methods,  variance explained {100*e:.0f}%)")
    ax.set_xlabel("inter-scanner |a-1|  (lower = more reproducible)")
    ax.grid(axis="x", alpha=0.3)
fig.suptitle("Harmonization reproducibility by pipeline stage (HD-BET run)", fontsize=13)
plt.tight_layout(rect=(0, 0, 1, 0.97))
plt.savefig(out, dpi=130)
print("wrote", out)

# variance-explained table (all metrics x stages)
print("\nvariance explained (eta^2, one-way):")
print(f"{'metric':16s} " + " ".join(f"{s:>13s}" for s in STAGES))
for key, label in METRICS:
    print(f"{label:16s} " + " ".join(f"{100*eta2(main, s, key):12.0f}%" for s in STAGES))
