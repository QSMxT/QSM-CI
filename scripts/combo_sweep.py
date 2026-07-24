#!/usr/bin/env python3
"""Combination (joint) parameter sweep for QSM-CI — does a method's ISOLATED-tuned value stay
optimal once it's CHAINED behind another method?

scripts/sweep.py tunes each method alone (fed ground-truth inputs). But in the composed matrix a
dipole method inverts the *output field of a BFR method*, not the ground-truth local field — so its
optimal regularisation may shift depending on which BFR feeds it. This script measures that: for each
(bfr -> dipole) cell it runs the BFR once, then sweeps the downstream dipole's grid over that BFR's
actual localfield and scores the final chimap's xSIM against ground truth.

  python scripts/combo_sweep.py --dataset data/sim/dev [--bfr sharp,resharp] [--dipole tv,nltv]
  python scripts/combo_sweep.py --dataset data/sim/dev --sweep-bfr   # also vary the BFR's own param

Default strategy = "downstream" (hold the BFR at its default, sweep only the dipole): this is the
cheap ~264-run probe that answers "does the dipole optimum move with the upstream BFR?". Pass
--sweep-bfr to additionally vary a tunable BFR's parameter (recomputing its localfield per value) —
the fuller joint grid. Results go to results/combo_sweep.json; scripts/combo_sweep_report.py reads
them and prints, per cell, whether the isolated-tuned point coincides with the in-combination best.

Field-mapping is held at the ground-truth totalfield ("gt" source) — neither field-map submission
declares a tunable knob, so there is nothing to sweep on that axis. Spans (tgv, matlab-medi) are
single-step and have no combination to tune; their isolated sweep already covers them.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import itertools
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import (  # noqa: E402  reuse the exact composed-chain machinery
    ARTIFACT_FILE, discover_algorithms, prepare_input, run_algo, _valid_mask,
)
from sweep import GRIDS, REFINE, combos, fmt, gt_sources  # noqa: E402  one grid definition, shared

# Which stages each swept slug belongs to is decided from discover_algorithms(), not hardcoded — so
# the split below is derived at runtime. GRIDS/REFINE already list every method with a tunable knob.

_print_lock = threading.Lock()
RUNNER = "docker"


def score_chi_xsim(recon: Path, gt_dir: Path, mask: Path, work: Path) -> dict:
    """Score a composed chimap's xSIM vs ground truth — same valid-mask + qsm_eval path as
    pipeline.score / sweep.score_xsim, so combo numbers are comparable to the leaderboard's."""
    sm = _valid_mask(recon, mask, work.with_suffix(".scoremask.nii.gz"))
    out_json = work.with_suffix(".score.json")
    cmd = [sys.executable, str(EVAL), "--recon", str(recon),
           "--truth", str(gt_dir / ARTIFACT_FILE["chimap"]), "--kind", "chi",
           "--mask", str(sm), "--artifact", "chimap", "--out", str(out_json),
           "--stage", "combo-sweep", "--name", "combo-sweep", "--track", "sim"]
    seg = gt_dir / "dseg.nii.gz"
    if seg.exists():
        cmd += ["--seg", str(seg)]
    subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(out_json.read_text())["metrics"]


def run_bfr(bfr: dict, override: dict, src: dict, work: Path) -> "tuple | None":
    """Run one BFR (at `override`, {} = default) on the gt totalfield; return (localfield, valid
    mask, runtime) or None on DNF. Mirrors pipeline.do_bfr: run within the incoming mask, then narrow
    the mask to the BFR's non-zero support so the dipole never inverts a zero-field rim."""
    tag = "__".join(f"{k}-{fmt(v)}" for k, v in override.items()) or "default"
    idir, odir = work / f"bfr_{bfr['slug']}__{tag}__in", work / f"bfr_{bfr['slug']}__{tag}__out"
    try:
        prepare_input(bfr["consumes"], src, idir)
        rt = run_algo(bfr, idir, odir, RUNNER, override or None)
        lf = odir / ARTIFACT_FILE["localfield"]
        lf_mask = _valid_mask(lf, src["mask"], odir / "validmask.nii.gz")
        return (lf, lf_mask, rt)
    except Exception as e:  # noqa: BLE001
        with _print_lock:
            print(f"  bfr  {bfr['slug']:<14} {tag:<24} DNF ({str(e)[-120:]})", flush=True)
        return None


def run_dipole(dipole: dict, override: dict, src: dict, work: Path) -> dict:
    """Invert a cached localfield with one dipole grid point; score the final chimap's xSIM."""
    tag = "__".join(f"{k}-{fmt(v)}" for k, v in override.items()) or "default"
    idir, odir = work / f"{work.name}_dip_{dipole['slug']}__{tag}__in", \
        work / f"{work.name}_dip_{dipole['slug']}__{tag}__out"
    rec = {"dipole": dipole["slug"], "override": override, "tag": tag}
    try:
        prepare_input(dipole["consumes"], src, idir)
        t0 = time.time()
        run_algo(dipole, idir, odir, RUNNER, override or None)
        m = score_chi_xsim(odir / ARTIFACT_FILE["chimap"], Path(src["chimap"]).parent,
                           src["mask"], work / f"dip_{dipole['slug']}__{tag}")
        rec.update(status="ok", xsim=m.get("xsim"), nrmse=m.get("nrmse"), runtime=time.time() - t0)
    except subprocess.CalledProcessError as e:
        rec.update(status="DNF", error=(e.stderr or "")[-300:])
    except Exception as e:  # noqa: BLE001
        rec.update(status="DNF", error=str(e)[-300:])
    return rec


def _tuned_point(algo: dict) -> "dict | None":
    """The method's isolated-tuned override (from algorithm.yml `tuned:`), coerced onto its grid's
    keys, or None if it declares no tuned value for a swept param. Used to guarantee the joint sweep
    always measures the isolated optimum so the report can compare it to the joint best."""
    tuned = algo.get("tuned") or {}
    grid = GRIDS.get(algo["slug"], {})
    pt = {k: tuned[k] for k in grid if k in tuned}
    return pt or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/sim/dev",
                    help="tune on dev; confirm winners on data/sim/scoring separately (dev avoids "
                         "overfitting the scored phantom any harder than isolated tuning already does)")
    ap.add_argument("--bfr", default=None, help="comma-separated BFR slugs (default: all localfield producers)")
    ap.add_argument("--dipole", default=None, help="comma-separated dipole slugs (default: all tunable dipoles)")
    ap.add_argument("--sweep-bfr", action="store_true",
                    help="also vary each tunable BFR's own parameter, recomputing its localfield per "
                         "value (the fuller joint grid). Default holds the BFR at its built-in default.")
    ap.add_argument("--refine", action="store_true", help="use the round-2 REFINE grids where defined")
    ap.add_argument("--jobs", type=int, default=4, help="MATLAB MCR runs are memory-heavy; keep modest")
    ap.add_argument("--runner", default="docker", help="docker/podman/apptainer/local")
    ap.add_argument("--work", type=Path, default=ROOT / ".combo_sweep")
    ap.add_argument("--out", type=Path, default=ROOT / "results/combo_sweep.json")
    args = ap.parse_args()
    global RUNNER
    RUNNER = args.runner
    grids = REFINE if args.refine else GRIDS

    src0 = gt_sources(args.dataset)  # "gt" field-map source = ground-truth totalfield
    algos = {a["slug"]: a for a in discover_algorithms()}

    bfrs = [a for a in algos.values() if "localfield" in a["produces"]]
    dipoles = [a for a in algos.values() if a["stage"] == "dipole" and a["slug"] in grids]
    if args.bfr:
        want = set(args.bfr.split(","));  bfrs = [b for b in bfrs if b["slug"] in want]
    if args.dipole:
        want = set(args.dipole.split(","));  dipoles = [d for d in dipoles if d["slug"] in want]
    if not bfrs or not dipoles:
        raise SystemExit("nothing to sweep — check --bfr/--dipole against the tunable methods")

    # BFR variants: default only, unless --sweep-bfr and the BFR has a grid.
    def bfr_variants(b):
        vs = [{}]
        if args.sweep_bfr and b["slug"] in grids:
            vs += [ov for ov in combos(grids[b["slug"]]) if ov]
        return vs

    n_bfr_runs = sum(len(bfr_variants(b)) for b in bfrs)
    n_dip_pts = sum(len(combos(grids[d["slug"]])) + 1 for d in dipoles)  # +1 for true default
    print(f"combo sweep: {len(bfrs)} BFR x {len(dipoles)} dipole on {args.dataset.name}")
    print(f"  ~{n_bfr_runs} BFR localfield runs, up to ~{n_bfr_runs * n_dip_pts} dipole runs, "
          f"jobs={args.jobs}, strategy={'joint (BFR swept)' if args.sweep_bfr else 'downstream'}\n")
    args.work.mkdir(parents=True, exist_ok=True)

    # Stage 1 — compute every needed localfield once, keyed (bfr_slug, bfr_tag). Keying by the BFR's
    # override (not just its slug) is essential: pipeline.py's lf_cache omits the param dimension, so
    # a naive reuse would silently hand a dipole the wrong (default-param) field under --sweep-bfr.
    bfr_tasks = [(b, ov) for b in bfrs for ov in bfr_variants(b)]
    lf_cache: dict[tuple, tuple] = {}

    def do_bfr(task):
        b, ov = task
        tag = "__".join(f"{k}-{fmt(v)}" for k, v in ov.items()) or "default"
        res = run_bfr(b, ov, src0, args.work)
        if res:
            with _print_lock:
                print(f"  bfr  {b['slug']:<14} {tag:<24} ok ({res[2]:.0f}s)", flush=True)
        return ((b["slug"], tag), res)

    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        for key, res in ex.map(do_bfr, bfr_tasks):
            if res:
                lf_cache[key] = res

    # Stage 2 — for each cached localfield, sweep every dipole's grid (plus the true default and the
    # dipole's isolated-tuned point, so the report can always compare isolated-vs-joint).
    dip_tasks = []
    for (bfr_slug, bfr_tag), (lf, lf_mask, up_rt) in lf_cache.items():
        cell_src = dict(src0); cell_src["localfield"] = lf; cell_src["mask"] = lf_mask
        cell_work = args.work / f"cell_{bfr_slug}__{bfr_tag}"
        cell_work.mkdir(parents=True, exist_ok=True)
        for d in dipoles:
            pts = [{}] + combos(grids[d["slug"]])           # {} = the method's built-in default
            tp = _tuned_point(d)
            if tp and tp not in pts:
                pts.append(tp)                               # ensure isolated-tuned is measured
            seen = set()
            for ov in pts:
                k = tuple(sorted((kk, fmt(vv)) for kk, vv in ov.items()))
                if k in seen:
                    continue
                seen.add(k)
                dip_tasks.append((bfr_slug, bfr_tag, up_rt, d, ov, cell_src, cell_work))

    results = []

    def do_dip(task):
        bfr_slug, bfr_tag, up_rt, d, ov, cell_src, cell_work = task
        rec = run_dipole(d, ov, cell_src, cell_work)
        rec.update(bfr=bfr_slug, bfr_tag=bfr_tag, upstream_runtime=up_rt,
                   fieldmap="gt", dataset=args.dataset.name,
                   isolated_tuned=_tuned_point(d) or {})
        with _print_lock:
            x = f"xsim={rec['xsim']:.4f}" if rec.get("xsim") is not None else "DNF"
            print(f"  {bfr_slug}+{d['slug']:<12} {rec['tag']:<24} {x}", flush=True)
        return rec

    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        results = list(ex.map(do_dip, dip_tasks))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nwrote {args.out}  ({len(results)} dipole runs across {len(lf_cache)} localfields)")
    print("run  scripts/combo_sweep_report.py  to see isolated-tuned vs in-combination best")


if __name__ == "__main__":
    main()
