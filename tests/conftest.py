"""Shared fixtures for the test suite.

`pipeline` loads scripts/pipeline.py ONCE per session as a module object. It is a standalone script
(no package), so the test files used to each exec it from its file path — three distinct module
objects, three `sys.path.insert(0, ROOT)` side effects. scripts/ is on sys.path for the session via
pyproject's `[tool.pytest.ini_options] pythonpath`, so a plain import resolves it, and `sys.modules`
caching means every consumer shares the same object.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(scope="session")
def pipeline():
    """scripts/pipeline.py as a module (the composed/isolated scorer's functions and tables)."""
    return importlib.import_module("pipeline")


@pytest.fixture(scope="session")
def repro_payload(tmp_path_factory):
    """A small harmonization payload written by the real writers: synthetic per-ROI means for a few
    live pipelines on every registry acquisition (results/repro_rois.json), then `repro_eval.py fits`
    and gen_repro_regions.py into a scratch results/ dir, one payload set per cohort. Built to exercise
    every branch the payload records, in EVERY cohort: a pipeline that misses one acquisition (no
    reconstruction), a diverged slope (rejected), a flat ROI cloud (rejected), too few common ROIs
    (rejected), and a pipeline built on a method the manifest no longer defines (dropped). Plus a
    pipeline that only ran on the traveling heads, so it must be in that cohort's payload and absent
    from the pilot's. Returns (results dir, {pipeline: {acq: {roi: mean}}})."""
    import json
    import random
    import subprocess
    import sys
    from pathlib import Path

    repro_eval = importlib.import_module("repro_eval")
    root = Path(__file__).resolve().parent.parent
    out = tmp_path_factory.mktemp("repro") / "results"
    out.mkdir()
    acqs = repro_eval.repro_acquisitions()
    labels = sorted(repro_eval.ROI_LABELS)
    rng = random.Random(7)
    truth = {s: {lab: rng.uniform(-0.05, 0.15) for lab in labels} for s in {a["subject"] for a in acqs.values()}}
    pipes = ["romeo-qsmrs+vsharp-qsmrs+rts-qsmrs", "laplacian-qsmrs+pdf-qsmrs+tv-qsmrs", "iqsm",
             "romeo-qsmrs+retired-bfr+rts-qsmrs", "tgv-qsmrs"]
    heads_only = "tgv-qsmrs"
    # the first four acquisitions of each cohort carry that cohort's anomalies
    firsts = [sorted(k for k, a in acqs.items() if a["group"] == g) for g in repro_eval.REPRO_GROUPS]
    first = {i: {f[i] for f in firsts if len(f) > i} for i in range(4)}
    rois: dict = {}
    for p in pipes:
        for a in sorted(acqs):
            if p == heads_only and acqs[a]["group"] != "harmonization":
                continue                                         # never ran on the pilot
            if p == pipes[1] and a in first[0]:
                continue                                         # no reconstruction
            gain = rng.uniform(0.8, 1.2)
            if p == "iqsm" and a in first[1]:
                gain = 4.5                                       # slope far outside the cap
            vals = {lab: gain * truth[acqs[a]["subject"]][lab] + rng.gauss(0, 0.004) for lab in labels}
            if p == "iqsm" and a in first[2]:
                vals = {lab: 0.01 for lab in labels}             # flat cloud
            if p == pipes[0] and a in first[3]:
                vals = {lab: vals[lab] for lab in labels[:5]}    # too few ROIs
            rois[(p, a)] = vals
    runs = {f"r{i}": {"pipeline": p, "acq": a, "status": "ok", "rois": v,
                      "roi_stats": {str(k): {"n": 100 + k, "mean": m} for k, m in v.items()}}
            for i, ((p, a), v) in enumerate(rois.items())}
    (out / "repro_rois.json").write_text(json.dumps({"runs": runs}))
    mp = pytest.MonkeyPatch()
    mp.setattr(repro_eval, "RESULTS", out)
    try:
        repro_eval.cmd_fits(None)
    finally:
        mp.undo()
    subprocess.run([sys.executable, str(root / "scripts" / "gen_repro_regions.py"),
                    str(out / "repro_rois.json"), str(out)], check=True, capture_output=True)
    by: dict = {}
    for (p, a), v in rois.items():
        by.setdefault(p, {})[a] = v
    return out, by
