#!/usr/bin/env python3
"""Parameter sweep for QSM-CI algorithms — optimise isolated xSIM.

Runs each tunable algorithm over a grid of --set overrides in ISOLATED mode (fed the ground-truth
artifact(s) its stage consumes, exactly like scripts/pipeline.py isolated), scores each output's
xSIM against ground truth with the same valid-mask logic as the pipeline, and reports the best grid
point per algorithm against its current default.

  python scripts/sweep.py --dataset data/sim/scoring [--only tgv,tkd] [--jobs 4]

The χ-separation stage is supported too: those methods emit TWO source maps (χ+ and χ−), each scored
with `--kind chisep`, and the sweep's objective is the mean of the two xSIMs (both are reported so a
human can favour χ+ or χ− when picking a tuned value). Point it at the chisep dataset and restrict to
the chisep slugs:

  python scripts/sweep.py --dataset data/sim/chisep --only wavesep,chi-sep-medi,chi-sep-ilsqr

Writes results/sweep.json (every grid point) and prints a per-algorithm best-vs-baseline table.
Only regularisation / threshold knobs are swept — pure convergence knobs (tol, max_iter) are held at
their defaults, since they change convergence, not the over-/under-regularisation we're tuning for.
The two χ-separation deep nets are intentionally NOT swept: susep-net exposes no knob, and χ-sepnet's
only knob (Dr) is baked into its trained weights, so moving it feeds off-distribution inputs rather
than tuning accuracy.
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
# Put the repo root on sys.path so `qsm_ci` resolves straight from a bare checkout (same pattern as
# pipeline.py). scripts/ is on the path too for the pipeline helpers we still reuse (run_algo etc.).
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from qsm_ci.scoring import cli_run_argv, gt_sources, eval_argv  # noqa: E402  shared primitives
from pipeline import (  # noqa: E402  reuse the exact isolated-scoring machinery
    ARTIFACT_FILE, ARTIFACT_KIND, discover_algorithms, prepare_input, _valid_mask,
)

# Grid of {param: [values]} per slug. itertools.product expands to one run per combination.
# Baselines (current defaults) are included so the sweep re-measures them under identical scoring.
GRIDS: dict[str, dict[str, list]] = {
    # --- dipole stage (fast qsmxt inversions) ---
    "tkd-qsmrs":      {"threshold": [0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3]},
    "tsvd-qsmrs":     {"threshold": [0.05, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3]},
    "tikhonov-qsmrs": {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2]},
    "medi-qsmrs":     {"lambda": [3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2]},
    "tv-qsmrs":       {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3]},
    "nltv-qsmrs":     {"lambda": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3]},
    "rts-qsmrs":      {"delta": [0.3, 0.6, 1.0, 1.5, 2.0, 3.0], "mu": [1.0]},
    # --- background-field removal (already scores high; sweep reg/threshold anyway) ---
    "resharp-qsmrs":  {"radius": [8.0, 12.0, 15.0, 20.0], "tik_reg": [1e-4, 1e-3, 5e-3]},
    "sharp-qsmrs":    {"threshold": [0.01, 0.02, 0.05, 0.1]},
    "vsharp-qsmrs":   {"threshold": [0.01, 0.02, 0.05, 0.1]},
    # --- bfr+dipole single-step spans (the over-regularised ones) ---
    "tgv-qsmrs":      {"alpha1": [0.0002, 0.0004, 0.0006, 0.001], "alpha0": [0.0008, 0.0015, 0.0025]},
    "medi-cornell": {"lambda": [100, 300, 600, 1000], "smv_radius": [3, 5]},
    # --- unwrap+bfr ---
    "harperella-qsmrs":  {"radius": [3.0, 5.0, 8.0]},
    "iharperella-qsmrs": {"radius": [3.0, 5.0, 8.0]},
    # --- chi-separation (iterative only; run with --dataset data/sim/chisep) ---
    # wavesep: wavelet-L1 sparsity weight (primary knob) x proximal-gradient step. Dr is left at the
    # phantom's known kernel (137) — sweeping a physical constant on the phantom that defines it is
    # circular, and it's exposed for callers who want it. max_iter (convergence) held at default.
    "wavesep":       {"lambda": [0.005, 0.01, 0.02, 0.04, 0.08], "alpha": [0.1, 0.2, 0.4]},
    # chi-sep-medi: MEDI data-fidelity/morphology regularisation weight (params.lambda).
    "chisep-medi":  {"lambda": [0.1, 0.3, 1.0, 3.0, 10.0]},
    # chi-sep-ilsqr: padding for the in-house QSM_iLSQR step (boundary/wrap artifacts). A numerical
    # knob rather than a regularisation one, but it's the only lever the black-box toolbox exposes.
    "chisep-ilsqr": {"pad_size": [8, 12, 16, 20]},
}

# Round-2 refinement: extend the axes where round-1's best sat on a grid edge, so the true optimum
# isn't clipped. Only these slugs are re-run (with --refine).
REFINE: dict[str, dict[str, list]] = {
    "tgv-qsmrs":     {"alpha1": [0.00003, 0.00006, 0.0001, 0.00015, 0.0002], "alpha0": [0.0015]},
    "tsvd-qsmrs":    {"threshold": [0.02, 0.03, 0.04, 0.05, 0.06]},
    "nltv-qsmrs":    {"lambda": [3e-3, 1e-2, 3e-2, 1e-1]},
    "sharp-qsmrs":   {"threshold": [0.003, 0.005, 0.008, 0.01]},
    "vsharp-qsmrs":  {"threshold": [0.1, 0.15, 0.2, 0.3]},
    "harperella-qsmrs": {"radius": [1.0, 2.0, 3.0]},
    # λ climbs to 0.546 at 450 but diverges hard by 600 — pin the peak in the pre-cliff window.
    "medi-cornell": {"lambda": [460, 480, 500, 520, 540, 560], "smv_radius": [5]},
    # --- chi-separation round-2 (PROVISIONAL: re-center on round-1's best before use) ---
    # Finer log-brackets around each method's primary regularisation knob. Unlike the entries above —
    # which were narrowed to where round-1 actually peaked — these are seeded from the round-1 grid's
    # interesting middle because the χ-sep sweep hasn't been run yet (no containers/data in this env).
    # Once round-1 exists, re-center on its best (and pin wavesep's alpha to round-1's best alpha, not
    # the 0.2 default assumed here). pad_size (ilsqr) is already dense in round-1, so it has no round-2.
    "wavesep":      {"lambda": [0.008, 0.012, 0.016, 0.02, 0.028, 0.04, 0.06], "alpha": [0.2]},
    "chisep-medi": {"lambda": [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]},
}

_print_lock = threading.Lock()
RUNNER = "docker"


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
    seg = gt / "dseg.nii.gz"
    cmd = eval_argv(sys.executable, EVAL, recon, gt / ARTIFACT_FILE[artifact], kind, sm,
                    artifact, out_json, stage="sweep", name="sweep", track="sim",
                    seg=seg if (kind == "chi" and seg.exists()) else None)
    subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(out_json.read_text())["metrics"]


def is_chisep(algo: dict) -> bool:
    """A χ-separation run: >1 produced artifact, all of kind 'chisep' (χ+ and χ−) — same test the
    pipeline uses to route to its two-output scorer."""
    prods = algo["produces"]
    return len(prods) > 1 and all(ARTIFACT_KIND.get(p) == "chisep" for p in prods)


def score_chisep(odir: Path, gt: Path, mask: Path, work: Path) -> dict:
    """Score a χ-separation run's two source maps (χ+ = chi-para, χ− = chi-dia) against ground truth,
    each with `--kind chisep`, using the same valid-mask logic as the QSM path. Returns
    {para_xsim, dia_xsim, para_nrmse, dia_nrmse}. seg (dseg) is passed when present so the recorded
    metrics include the region-specific leakage, matching pipeline.score."""
    seg = gt / "dseg.nii.gz"
    out: dict = {}
    for art, comp in (("chi-para", "para"), ("chi-dia", "dia")):
        recon = odir / ARTIFACT_FILE[art]
        sm = _valid_mask(recon, mask, work.with_suffix(f".{comp}.scoremask.nii.gz"))
        out_json = work.with_suffix(f".{comp}.score.json")
        cmd = eval_argv(sys.executable, EVAL, recon, gt / ARTIFACT_FILE[art], "chisep", sm,
                        art, out_json, stage="sweep", name="sweep", track="chisep",
                        seg=seg if seg.exists() else None, component=comp)
        subprocess.run(cmd, check=True, capture_output=True)
        m = json.loads(out_json.read_text())["metrics"]
        out[f"{comp}_xsim"] = m.get("xsim")
        out[f"{comp}_nrmse"] = m.get("nrmse")
    return out


def _f4(v) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) else "n/a"


def run_one(algo: dict, override: dict, src: dict, gt_dir: Path, work: Path) -> dict:
    slug = algo["slug"]
    tag = "__".join(f"{k}-{fmt(v)}" for k, v in override.items()) or "default"
    idir = work / f"{slug}__{tag}__in"
    odir = work / f"{slug}__{tag}__out"
    prepare_input(algo["consumes"], src, idir)  # stage GT inputs under canonical names
    # Shared argv builder — `fmt=fmt` reproduces the sweep's grid-value formatting (a swept float like
    # 8.0 renders as `8`, this script's long-standing behaviour), so the emitted argv is unchanged.
    # For a χ-separation (multi-output) method it hands the CLI the output DIR, not a single file.
    argv = cli_run_argv(algo, idir, odir, ARTIFACT_FILE, RUNNER, override, fmt=fmt)
    rec = {"slug": slug, "stage": algo["stage"], "override": override, "tag": tag}
    chisep = is_chisep(algo)
    try:
        odir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        subprocess.run(argv, check=True, capture_output=True, text=True)
        if chisep:
            m = score_chisep(odir, gt_dir, src["mask"], work / f"{slug}__{tag}")
            xs = [m[k] for k in ("para_xsim", "dia_xsim") if m.get(k) is not None]
            # Objective: mean of the two source xSIMs (both are also recorded so a human can favour one).
            rec.update(status="ok", xsim=(sum(xs) / len(xs) if xs else None),
                       para_xsim=m.get("para_xsim"), dia_xsim=m.get("dia_xsim"),
                       para_nrmse=m.get("para_nrmse"), dia_nrmse=m.get("dia_nrmse"),
                       runtime=time.time() - t0)
        else:
            produced = algo["produces"][0]
            m = score_xsim(odir / ARTIFACT_FILE[produced], produced,
                           gt_dir, src["mask"], work / f"{slug}__{tag}")
            rec.update(status="ok", xsim=m.get("xsim"), nrmse=m.get("nrmse"), runtime=time.time() - t0)
    except subprocess.CalledProcessError as e:
        rec.update(status="DNF", error=(e.stderr or "")[-400:])
    except Exception as e:  # noqa: BLE001
        rec.update(status="DNF", error=str(e)[-400:])
    with _print_lock:
        if rec.get("xsim") is None:
            x = "DNF"
        elif chisep:
            x = f"xsim={rec['xsim']:.4f} (χ+={_f4(rec.get('para_xsim'))} χ−={_f4(rec.get('dia_xsim'))})"
        else:
            x = f"xsim={rec['xsim']:.4f}"
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
    gt_dir = args.dataset / "groundtruth"   # scored artifacts (chimap / chi-para / chi-dia / dseg) live here
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
        results = list(ex.map(lambda t: run_one(t[0], t[1], src, gt_dir, args.work), tasks))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n")

    print("\n=== best grid point per algorithm (xSIM) ===")
    for slug in want:
        rs = [r for r in results if r["slug"] == slug and r.get("status") == "ok"]
        if not rs:
            print(f"{slug:<14} all DNF"); continue
        rs.sort(key=lambda r: r["xsim"], reverse=True)
        best, worst = rs[0], rs[-1]
        # χ-separation optimises the mean of χ+/χ− xSIM — show both components on the winning point so
        # a reviewer can still favour one source before writing the tuned value into algorithm.yml.
        extra = (f"  [χ+={_f4(best.get('para_xsim'))} χ−={_f4(best.get('dia_xsim'))}]"
                 if best.get("para_xsim") is not None else "")
        print(f"{slug:<14} best xsim={best['xsim']:.4f} @ {best['tag']:<26} "
              f"(range {worst['xsim']:.4f}–{best['xsim']:.4f} over {len(rs)} pts){extra}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
