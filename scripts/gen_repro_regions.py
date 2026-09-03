#!/usr/bin/env python3
"""Compact per-run regional aggregate for the harmonization Findings figures.

Reads results/repro_rois.json (per-run per-aseg-region chi, ~58 MB) and writes
results/repro_regions.json (~a few MB): for every run, its pipeline, acquisition,
and L/R-merged mean chi (ppb, 1 dp) per structure. The web computes every regional
figure live from this one small file, same deploy path as results/repro.json, so
re-running it on each harmonization publish keeps the figures current.

Usage: python scripts/gen_repro_regions.py [in=results/repro_rois.json] [out=results/repro_regions.json]
"""
import json, sys, math
from collections import defaultdict

IN = sys.argv[1] if len(sys.argv) > 1 else "results/repro_rois.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results/repro_regions.json"

# aseg id -> L/R-merged structure (matches ROI_LABELS in scripts/repro_eval.py)
GROUP = {
    "Cerebral-WM": [2, 41], "Cortex": [3, 42], "Cerebellum-WM": [7, 46], "Cerebellum-Ctx": [8, 47],
    "Thalamus": [10, 49], "Caudate": [11, 50], "Putamen": [12, 51], "Pallidum": [13, 52],
    "Hippocampus": [17, 53], "Amygdala": [18, 54], "Accumbens": [26, 58], "VentralDC": [28, 60],
    "Brain-Stem": [16],
}
ID2STRUCT = {str(i): s for s, ids in GROUP.items() for i in ids}

src = json.load(open(IN))
runs_in = src["runs"] if isinstance(src, dict) else src
out = []
for r in (runs_in.values() if isinstance(runs_in, dict) else runs_in):
    if r.get("status") and r["status"] != "ok":
        continue
    rs = r.get("roi_stats"); pipe = r.get("pipeline"); acq = r.get("acq")
    if not rs or not pipe or not acq:
        continue
    agg = defaultdict(lambda: [0.0, 0.0])
    for aid, s in rs.items():
        struct = ID2STRUCT.get(str(aid)); m = s.get("mean")
        if not struct or m is None or not s.get("n") or not math.isfinite(m) or abs(m) > 5:
            continue
        agg[struct][0] += m * s["n"]; agg[struct][1] += s["n"]
    means = {k: round(v[0] / v[1] * 1000, 1) for k, v in agg.items() if v[1] > 0}  # ppb, 1 dp
    if means:
        out.append({"p": pipe, "a": acq, "m": means})

doc = {"target": src.get("target") if isinstance(src, dict) else None,
       "structures": list(GROUP.keys()), "runs": out}
with open(OUT, "w") as fh:
    json.dump(doc, fh, separators=(",", ":"))
print(f"wrote {OUT}: {len(out)} runs")
