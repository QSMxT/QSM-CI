#!/usr/bin/env python3
"""Parameter sweep for QSM-CI algorithms — optimise isolated xSIM.

Runs each tunable algorithm over a grid of --set overrides in ISOLATED mode (fed the ground-truth
artifact(s) its stage consumes, exactly like scripts/pipeline.py isolated), scores each output's
xSIM against ground truth with the same valid-mask logic as the pipeline, and reports the best grid
point per algorithm against its current default.

  python scripts/sweep.py --dataset data/sim/dev [--only tgv,tkd] [--jobs 4]

Writes results/sweep.json (every grid point) and prints a per-algorithm best-vs-baseline table.
Only regularisation / threshold knobs are swept — pure convergence knobs (tol, max_iter) are held at
their defaults, since they change convergence, not the over-/under-regularisation we're tuning for.
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
from pipeline import (  # noqa: E402  reuse the exact isolated-scoring machinery
    ARTIFACT_FILE, discover_algorithms, prepare_input, _valid_mask,
)

# Grid of {param: [values]} per slug. itertools.product expands to one run per combination.
# Baselines (current defaults) are included so the sweep re-measures them under identical scoring.
GRIDS: dict[str, dict[str, list]] = {
    # --- dipole stage (fast qsmxt inversions) ---
    "tkd":      {"threshold": [0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3]},
    "tsvd":     {"threshold": [0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3]},
    "tikhonov": {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2]},
    "medi":     {"lambda": [3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2]},
    "tv":       {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3]},
    "nltv":     {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3]},
    "rts":      {"delta": [0.3, 0.6, 1.0, 1.5, 2.0, 3.0], "mu": [1.0]},
    # --- background-field removal (already scores high; sweep reg/threshold anyway) ---
    "resharp":  {"radius": [8.0, 12.0, 15.0, 20.0], "tik_reg": [1e-4, 1e-3, 5e-3]},
    "sharp":    {"threshold": [0.01, 0.02, 0.05, 0.1]},
    "vsharp":   {"threshold": [0.01, 0.02, 0.05, 0.1]},
    # --- bfr+dipole single-step spans (the over-regularised ones) ---
    "tgv":      {"alpha1": [0.0002, 0.0004, 0.0006, 0.001], "alpha0": [0.0008, 0.0015, 0.0025]},
    "matlab-medi": {"lambda": [100, 300, 600, 1000], "smv_radius": [3, 5]},
    # --- unwrap+bfr ---
    "harperella":  {"radius": [3.0, 5.0, 8.0]},
    "iharperella": {"radius": [3.0, 5.0, 8.0]},
}

# Round-2 refinement: extend the axes where round-1's best sat on a grid edge, so the true optimum
# isn't clipped. Only these slugs are re-run (with --refine).
REFINE: dict[str, dict[str, list]] = {
    "tgv":     {"alpha1": [0.00003, 0.00006, 0.0001, 0.00015, 0.0002], "alpha0": [0.0015]},
    "tsvd":    {"threshold": [0.02, 0.03, 0.04, 0.05, 0.06]},
    "nltv":    {"lambda": [3e-3, 1e-2, 3e-2, 1e-1]},
    "sharp":   {"threshold": [0.003, 0.005, 0.008, 0.01]},
    "vsharp":  {"threshold": [0.1, 0.15, 0.2, 0.3]},
    "harperella": {"radius": [1.0, 2.0, 3.0]},
    # λ climbs to 0.546 at 450 but diverges hard by 600 — pin the peak in the pre-cliff window.
    "matlab-medi": {"lambda": [460, 480, 500, 520, 540, 560], "smv_radius": [5]},
}

_print_lock = threading.Lock()
RUNNER = "docker"


def gt_sources(dataset: Path) -> dict[str, Path]:
    inputs, gt = dataset / "inputs", dataset / "groundtruth"
    return {
        "phase": inputs / "phase.nii.gz", "magnitude": inputs / "magnitude.nii.gz",
        "mask": inputs / "mask.nii.gz", "params": inputs / "params.json",
        "totalfield": gt / "totalfield.nii.gz", "localfield": gt / "localfield.nii.gz",
        "chimap": gt / "chimap.nii.gz",
    }


def combos(grid: dict[str, list]) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(grid[k] for k in keys))]


def fmt(v) -> str:
    return f"{v:g}" if isinstance(v, float) else str(v)


def score_xsim(recon: Path, artifact: str, gt: Path, mask: Path, work: Path) -> dict:
    """Valid-mask + qsm_eval, identical to pipeline.score; returns the metrics dict."""
    kind = {"totalfield": "field", "localfield": "field", "chimap": "chi"}[artifact]
    sm = _valid_mask(recon, mask, work.with_suffix(".scoremask.nii.gz"))
    out_json = work.with_suffix(".score.json")
    cmd = [sys.executable, str(EVAL), "--recon", str(recon),
           "--truth", str(gt / ARTIFACT_FILE[artifact]), "--kind", kind,
           "--mask", str(sm), "--artifact", artifact, "--out", str(out_json),
           "--stage", "sweep", "--name", "sweep", "--track", "sim"]
    seg = gt / "dseg.nii.gz"
    if kind == "chi" and seg.exists():
        cmd += ["--seg", str(seg)]
    subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(out_json.read_text())["metrics"]


def run_one(algo: dict, override: dict, src: dict, work: Path) -> dict:
    slug = algo["slug"]
    tag = "__".join(f"{k}-{fmt(v)}" for k, v in override.items()) or "default"
    idir = work / f"{slug}__{tag}__in"
    odir = work / f"{slug}__{tag}__out"
    produced = algo["produces"][0]
    prepare_input(algo["consumes"], src, idir)  # stage GT inputs under canonical names
    argv = ["qsm-ci", "run", str(algo["dir"])]
    for art in algo["consumes"]:
        f = idir / ARTIFACT_FILE[art]
        if art == "magnitude" and not f.exists():
            continue
        argv += [f"--{art}", str(f)]
    for k, v in override.items():
        argv += ["--set", f"{k}={fmt(v)}"]
    argv += ["-o", str(odir / ARTIFACT_FILE[produced]), "--runner", RUNNER]
    rec = {"slug": slug, "stage": algo["stage"], "override": override, "tag": tag}
    try:
        odir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        subprocess.run(argv, check=True, capture_output=True, text=True)
        m = score_xsim(odir / ARTIFACT_FILE[produced], produced,
                       Path(src["chimap"]).parent, src["mask"], work / f"{slug}__{tag}")
        rec.update(status="ok", xsim=m.get("xsim"), nrmse=m.get("nrmse"), runtime=time.time() - t0)
    except subprocess.CalledProcessError as e:
        rec.update(status="DNF", error=(e.stderr or "")[-400:])
    except Exception as e:  # noqa: BLE001
        rec.update(status="DNF", error=str(e)[-400:])
    with _print_lock:
        x = f"xsim={rec['xsim']:.4f}" if rec.get("xsim") is not None else f"DNF"
        print(f"  {slug:<14} {tag:<28} {x}", flush=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/sim/scoring")
    ap.add_argument("--only", default=None, help="comma-separated slugs to restrict the sweep")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--refine", action="store_true", help="use the round-2 REFINE grids")
    ap.add_argument("--runner", default="docker", help="docker/podman/apptainer/local")
    ap.add_argument("--work", type=Path, default=ROOT / ".sweep")
    ap.add_argument("--out", type=Path, default=ROOT / "results/sweep.json")
    args = ap.parse_args()
    global RUNNER
    RUNNER = args.runner

    src = gt_sources(args.dataset)
    algos = {a["slug"]: a for a in discover_algorithms()}
    grids = REFINE if args.refine else GRIDS
    want = args.only.split(",") if args.only else list(grids)
    want = [s for s in want if s in grids]

    tasks = []
    for slug in want:
        a = algos.get(slug)
        if a is None:
            print(f"! {slug} not discovered — skipping"); continue
        tasks.append((a, {}))  # true no-override baseline (the method's built-in default)
        for ov in combos(grids[slug]):
            tasks.append((a, ov))
    print(f"sweeping {len(want)} algorithms, {len(tasks)} runs, jobs={args.jobs}\n")
    args.work.mkdir(parents=True, exist_ok=True)

    # MATLAB MCR runs are memory-heavy; keep the whole sweep at the given cap (default 4).
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        results = list(ex.map(lambda t: run_one(t[0], t[1], src, args.work), tasks))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n")

    print("\n=== best grid point per algorithm (xSIM) ===")
    for slug in want:
        rs = [r for r in results if r["slug"] == slug and r.get("status") == "ok"]
        if not rs:
            print(f"{slug:<14} all DNF"); continue
        rs.sort(key=lambda r: r["xsim"], reverse=True)
        best, worst = rs[0], rs[-1]
        print(f"{slug:<14} best xsim={best['xsim']:.4f} @ {best['tag']:<26} "
              f"(range {worst['xsim']:.4f}–{best['xsim']:.4f} over {len(rs)} pts)")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
