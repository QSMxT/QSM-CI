#!/usr/bin/env python3
"""Compact per-run regional aggregate for the harmonization Findings figures.

Reads results/repro_rois.json (per-run per-aseg-region chi, ~220 MB) and writes, for each
harmonization cohort (the registry's `group`, see scripts/repro_format.py REPRO_GROUPS),
results/<stem>_regions.json (a small index) + results/<stem>_regions.bin: the L/R-merged mean chi
(ppb, 1 dp) of every structure for every run on that cohort's acquisitions, as one float32 grid
[pipeline x acquisition x structure] with NaN where a pipeline has no run (or no value) on an
acquisition — the layout scripts/repro_format.py describes. So results/repro_regions.* are the
traveling heads and results/repro_pilot_regions.* the MGH pilot. The web computes every regional
figure live from them, same deploy path as the cohort's results/<stem>.json, so re-running it on
each harmonization publish keeps the figures current.

Each index also carries its acquisitions' {subject, scanner, protocol, run} (from
scripts/datasets.json) and the per-subject registration targets, so the figures pair acquisitions
from metadata rather than by parsing ids.

Usage: python scripts/gen_repro_regions.py [in=results/repro_rois.json] [out_dir=results]
"""
import json, sys, math, os
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repro_format import REPRO_GROUPS, group_of, payload_names, write_columns  # noqa: E402

IN = sys.argv[1] if len(sys.argv) > 1 else "results/repro_rois.json"
OUT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "results")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(_ROOT, "web", "algorithms.json")
REGISTRY = os.path.join(_ROOT, "scripts", "datasets.json")
ACQ_FIELDS = ("subject", "scanner", "protocol", "run")

# Methods the manifest still defines. A method REMOVED from algorithms.json is gone from
# QSM-CI, so its runs shouldn't be republished here on every harvest; `hidden: true` is the other
# state — parked but revivable (the MATLAB amp-pe) — and those stay, hidden by the web. Same rule as
# repro_eval.py's live_algo_slugs(), duplicated rather than imported so this stays a dependency-free
# post-processing step.
LIVE = ({a["slug"] for a in json.load(open(MANIFEST)).get("algorithms", []) if a.get("slug")}
        if os.path.exists(MANIFEST) else set())
retired = set()

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
    if LIVE and not all(s in LIVE for s in pipe.split("+")):
        retired.update(s for s in pipe.split("+") if s not in LIVE)
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

# Don't overwrite a good payload with an empty one. The usual cause is an input written before
# _roi_row() started emitting `roi_stats` (it carries only `rois`, the plain means): re-run
# `repro_eval.py stats` where the recons live to refresh it, rather than shipping 0 runs.
if not out:
    stale = any(r.get("rois") and not r.get("roi_stats")
                for r in (runs_in.values() if isinstance(runs_in, dict) else runs_in))
    sys.exit(f"no runs to write — refusing to overwrite the regions payloads in {OUT_DIR}.\n" + (
        f"{IN} has `rois` but no `roi_stats`: it predates the per-ROI stats field. "
        "Re-run `python scripts/repro_eval.py stats` where the harmonization recons live."
        if stale else f"{IN} yielded no usable rows."))

# Acquisition metadata and cohort for every repro-track acquisition (same fields repro.json carries).
reg = json.load(open(REGISTRY)) if os.path.exists(REGISTRY) else {}
repro_reg = {k: v for k, v in sorted(reg.items()) if v.get("track") == "repro"}
unknown = sorted({group_of(v) for v in repro_reg.values()} - set(REPRO_GROUPS))
if unknown:
    sys.exit(f"scripts/datasets.json names harmonization group(s) {unknown} that "
             "scripts/repro_format.py REPRO_GROUPS does not define")
src_targets = (src.get("targets") if isinstance(src, dict) else None) or {}
structures = list(GROUP.keys())
unregistered = sorted({r["a"] for r in out} - set(repro_reg))
if unregistered:
    print(f"skipped runs on acquisitions not in scripts/datasets.json: {', '.join(unregistered)}")

for group in REPRO_GROUPS:
    mine = {k: v for k, v in repro_reg.items() if group_of(v) == group}
    rows = [r for r in out if r["a"] in mine]
    names = payload_names(group)
    if not rows:
        # Same rule per cohort: one with no runs keeps whatever payload it has.
        print(f"{group}: no runs on its acquisitions — left {names['regions']} as it is")
        continue
    seen = {r["a"] for r in rows}
    acquisitions = {k: {f: v.get(f) for f in ACQ_FIELDS} for k, v in mine.items() if k in seen}
    subjects = {v["subject"] for v in mine.values() if v.get("subject")}
    targets = {s: t for s, t in src_targets.items() if s in subjects}
    if not targets:   # derive from the registry when the input predates per-subject targets
        targets = {v["subject"]: k for k, v in mine.items() if v.get("repro_target") and v.get("subject")}
    pipes, acqs = sorted({r["p"] for r in rows}), sorted(seen)
    pi, ai = {p: i for i, p in enumerate(pipes)}, {a: i for i, a in enumerate(acqs)}
    grid = [None] * (len(pipes) * len(acqs) * len(structures))
    for r in rows:
        base = (pi[r["p"]] * len(acqs) + ai[r["a"]]) * len(structures)
        for k, st in enumerate(structures):
            grid[base + k] = r["m"].get(st)
    values = write_columns(OUT_DIR, [(names["regions_bin"], {"chi_ppb": grid})],
                           (len(pipes), len(acqs), len(structures)), {"chi_ppb": 1})
    doc = {"group": group, "targets": targets, "acquisitions": acquisitions, "structures": structures,
           "pipelines": pipes, "acqs": acqs, "values": values}
    with open(OUT_DIR / names["regions"], "w") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    print(f"{group}: wrote {OUT_DIR / names['regions']} + {names['regions_bin']}: {len(rows)} runs "
          f"({len(pipes)} pipelines x {len(acqs)} acquisitions x {len(structures)} structures)")
if retired:
    print(f"skipped runs built on methods no longer in algorithms.json: {', '.join(sorted(retired))}")
