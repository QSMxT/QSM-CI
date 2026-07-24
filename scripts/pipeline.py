#!/usr/bin/env python3
"""QSM-CI pipeline runner — isolated + composed evaluation.

Discovers stage submissions under algorithms/, runs them on a dataset, scores each produced
artifact with qsm-eval, and writes results/ entries. The `local` runner runs submissions directly
via their run.sh (no Docker) so it works locally; the `docker` runner (CI) delegates each run to the
installed `qsm-ci run` CLI, which pulls the prebuilt image, mounts run.sh, and injects QSMCI_* env
vars — one run path shared with the CLI, so the two harnesses can't drift.

Modes (see stages.yml):
  isolated  — feed each stage/span its GROUND-TRUTH consumed artifacts; score its outputs vs GT.
  composed  — chain bfr -> dipole (and spans) starting from GT totalfield; score the final chimap.
              bfr outputs are cached and reused across dipole methods (the N×M matrix).

Usage:
  python scripts/pipeline.py --dataset data/sim/dev [--mode isolated|composed|both] [--track sim]
"""

from __future__ import annotations

import argparse
import concurrent.futures as _cf
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"

# Independent submission runs (each a Docker container + a scoring subprocess) are executed
# concurrently, bounded by QSM_CI_JOBS. The cap is deliberately conservative: MATLAB MCR runs on
# the 205^3 volume peak at a few GB each, so 4 keeps well under the runner's ~31 GB. Set 1 for
# fully-serial behaviour. Threads are fine — the actual work is in subprocess.run (GIL released).
JOBS = max(1, int(os.environ.get("QSM_CI_JOBS", "4")))


def _pmap(items, fn):
    """Apply fn to each item, up to JOBS at a time, preserving input order. fn must handle its own
    errors (return a value, never raise) so one bad task can't sink the batch."""
    if JOBS <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with _cf.ThreadPoolExecutor(max_workers=JOBS) as ex:
        return list(ex.map(fn, items))

# Stage graph (mirrors stages.yml). Kept here so the runner needs no YAML dependency.
STAGES = {
    "field-mapping": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["totalfield"]},
    "bfr": {"consumes": ["totalfield", "mask", "params"], "produces": ["localfield"]},
    "dipole": {"consumes": ["localfield", "mask", "params"], "produces": ["chimap"]},
    "unwrap+bfr": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["localfield"]},
    "bfr+dipole": {"consumes": ["totalfield", "mask", "params", "magnitude"], "produces": ["chimap"]},
    "end-to-end": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["chimap"]},
}
ARTIFACT_FILE = {
    "phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
    "params": "params.json", "totalfield": "totalfield.nii.gz",
    "localfield": "localfield.nii.gz", "chimap": "chimap.nii.gz",
}
ARTIFACT_KIND = {"totalfield": "field", "localfield": "field", "chimap": "chi"}

EMIT_VOLUMES = False  # when set, write recon/truth/error NIfTIs per run for the web viewer


def emit_volumes(run_id, recon, truth, mask=None):
    """Write recon / truth / error volumes under results/<run_id>/ for the NiiVue viewer.

    The error map is the signed difference recon - truth, zeroed outside the raw brain mask so the
    background stays clean (the viewer shows it with a diverging red↔blue colormap)."""
    import nibabel as nib
    d = ROOT / "results" / run_id
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(recon, d / "recon.nii.gz")
    shutil.copy(truth, d / "truth.nii.gz")
    r, t = nib.load(str(recon)), nib.load(str(truth))
    err = (r.get_fdata() - t.get_fdata()).astype("float32")
    if mask is not None:
        err[nib.load(str(mask)).get_fdata() <= 0.5] = 0.0
    nib.save(nib.Nifti1Image(err, r.affine), str(d / "error.nii.gz"))


def _tuned_overrides(text: str) -> dict:
    """Extract `{param: tuned_value}` from an algorithm.yml `parameters:` block — the settings we
    optimised on the scoring phantom (each parameter may carry a `tuned:` alongside its `default:`).
    Regex, not YAML, to keep this module dependency-free like the rest of the runner. The block runs
    to the next top-level key (or EOF), NOT to the next non-space line — YAML list items may be
    unindented (`- name:` at column 0, as the MATLAB ymls write them), and those must not end it."""
    m = re.search(r"^parameters:[ \t]*\n(.*?)(?=^[A-Za-z_]|\Z)", text, re.M | re.S)
    if not m:
        return {}
    out = {}
    for item in re.split(r"^[ \t]*-[ \t]*name:[ \t]*", m.group(1), flags=re.M)[1:]:
        name = item.splitlines()[0].strip()
        tm = re.search(r"^[ \t]*tuned:[ \t]*(\S+)", item, re.M)
        if tm:
            out[name] = tm.group(1)
    return out


def discover_algorithms() -> list[dict]:
    algos = []
    for d in sorted((ROOT / "algorithms").glob("*/")):
        spec = d / "algorithm.yml"
        if d.name.startswith("_") or not spec.exists():
            continue
        text = spec.read_text()
        stage = re.search(r"^stage:\s*(\S+)", text, re.M)
        image = re.search(r"^image:\s*(\S+)", text, re.M)
        if not stage:
            continue
        s = stage.group(1)
        # A method may declare optional extra inputs (algorithm.yml `optional_inputs:`) beyond its
        # stage's baseline — e.g. MEDI (dipole) uses magnitude for edge weighting. Append them so the
        # scorer mounts + passes exactly what `qsm-ci run` accepts (its _consumes does the same);
        # otherwise it passes a flag the CLI rejects (--magnitude) and the run DNFs.
        opt = re.search(r"^optional_inputs:\s*\n((?:[ \t]*-[ \t]*\S+[ \t]*\n?)+)", text, re.M)
        optional = re.findall(r"-[ \t]*(\S+)", opt.group(1)) if opt else []
        consumes = STAGES[s]["consumes"] + [a for a in optional if a not in STAGES[s]["consumes"]]
        algos.append({
            "slug": d.name, "dir": d, "stage": s, "image": image.group(1) if image else None,
            "consumes": consumes, "produces": STAGES[s]["produces"],
            "tuned": _tuned_overrides(text),
        })
    return algos


def prepare_input(consumes: list[str], sources: dict[str, Path], dest: Path) -> None:
    """Populate dest with the consumed artifacts under their canonical filenames."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for art in consumes:
        src = sources.get(art)
        if src is None or not Path(src).exists():
            raise SystemExit(f"missing source artifact '{art}' (looked for {src})")
        shutil.copy(src, dest / ARTIFACT_FILE[art])


def _cli_run_argv(algo: dict, input_dir: Path, output_dir: Path,
                  runner: str = "docker", overrides: "dict | None" = None) -> list[str]:
    """Build the `qsm-ci run …` argv that reproduces this submission's isolated container run.

    Each consumed artifact becomes a `--<artifact> <input_dir>/<file>` flag (magnitude is optional —
    only passed when present); the produced artifact is written with `-o <output_dir>/<file>`. Any
    `overrides` become `--set NAME=VALUE` (the tuned pass). The CLI owns image resolution, mounting
    run.sh, and injecting the QSMCI_* acquisition env vars — so the scorer no longer duplicates
    (and drifts from) that logic."""
    produced = algo["produces"][0]
    argv = ["qsm-ci", "run", str(algo["dir"])]
    for art in algo["consumes"]:
        f = input_dir / ARTIFACT_FILE[art]
        if art == "magnitude" and not f.exists():
            continue  # optional — only some methods use it
        argv += [f"--{art}", str(f)]
    for k, v in (overrides or {}).items():
        argv += ["--set", f"{k}={v}"]
    argv += ["-o", str(output_dir / ARTIFACT_FILE[produced]), "--runner", runner]
    return argv


def run_algo(algo: dict, input_dir: Path, output_dir: Path, runner: str = "local",
             overrides: "dict | None" = None) -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    t0 = time.time()
    if runner != "local":
        # Delegate to the installed `qsm-ci` CLI (a console script) rather than reimplementing the
        # container run here. The CLI resolves the folder, pulls the prebuilt image, mounts run.sh
        # read-only, and injects the QSMCI_* env vars (TE/B0/…) — the very env vars this scorer used
        # to omit, which DNF'd submissions that read acquisition params through them.
        subprocess.run(_cli_run_argv(algo, input_dir, output_dir, runner, overrides), check=True)
    else:
        if overrides:  # run.sh reads overrides from $IN/config.json (mirrors `qsm-ci run --set`)
            (input_dir / "config.json").write_text(json.dumps(overrides))
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True)
    return time.time() - t0


def _valid_mask(volume: Path, base_mask: Path, out: Path) -> Path:
    """Write `base_mask ∧ (|volume| > 0)` — the region where a stage actually produced a value.

    Eroding stages (SHARP/V-SHARP/RESHARP/iSMV, Laplacian field-mapping, …) zero exactly the voxels
    they drop, so a field/χ's non-zero support IS the stage's valid region. Threading this as the
    mask into the next stage stops a dipole from deconvolving a zero-field rim (which smears a blurry
    boundary), and scoring within it stops that rim being counted as error. Empty output → keep the
    base mask so it still scores (badly) rather than crashing."""
    import nibabel as nib
    import numpy as np
    v = nib.load(str(volume))
    valid = np.abs(v.get_fdata()) > 0
    base = nib.load(str(base_mask)).get_fdata() > 0.5
    m = valid & base
    if not m.any():
        m = base
    nib.save(nib.Nifti1Image(m.astype(np.uint8), v.affine), str(out))
    return out


def _finite(v) -> bool:
    """True if v is a real, finite number — a usable metric, not None/NaN/inf."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _fmt(v, spec: str = ".4f") -> str:
    """Format a metric, or 'n/a' when it's missing/non-finite — so a NaN output can't crash a print."""
    return format(v, spec) if _finite(v) else "n/a"


def score(recon: Path, artifact: str, gt_dir: Path, mask: Path, out_json: Path, meta: dict) -> dict:
    kind = ARTIFACT_KIND[artifact]
    raw_mask = mask  # the full brain mask, before erosion — used to mask the viewer's error map
    # Score only where the method actually produced a value (its non-zero support), so an eroded
    # rim isn't penalised as error — consistent with masking that rim out of the pipeline.
    mask = _valid_mask(recon, mask, out_json.parent / (out_json.stem + "_scoremask.nii.gz"))
    cmd = [sys.executable, str(EVAL), "--recon", str(recon),
           "--truth", str(gt_dir / ARTIFACT_FILE[artifact]), "--kind", kind,
           "--mask", str(mask), "--artifact", artifact, "--out", str(out_json),
           "--stage", meta["stage"], "--name", meta["name"], "--track", meta["track"]]
    if meta.get("runtime") is not None:
        cmd += ["--runtime", str(meta["runtime"])]
    seg = gt_dir / "dseg.nii.gz"
    if kind == "chi" and seg.exists():
        cmd += ["--seg", str(seg)]
    subprocess.run(cmd, check=True)
    result = json.loads(out_json.read_text())
    # A scorable recon yields finite metrics; an all-NaN / empty output makes the scorer emit
    # null/NaN. Record that as a clear DNF (not a metric-less "ok" row, and without crashing the
    # caller's formatted print) so the failure is legible instead of a cryptic format-string error.
    primary = (result.get("metrics") or {}).get("xsim" if kind == "chi" else "nrmse")
    if _finite(primary):
        result["status"] = "ok"
    else:
        result["status"] = "DNF"
        result["dnf_reason"] = "non-finite output (unscorable)"
    result.update({k: meta[k] for k in ("id", "slug", "mode", "variant", "params") if k in meta})
    if "combo" in meta:
        result["combo"] = meta["combo"]
    if EMIT_VOLUMES and "id" in meta:
        emit_volumes(meta["id"], recon, gt_dir / ARTIFACT_FILE[artifact], raw_mask)
    return result


def dnf(rid, slug, name, stage, mode, track, combo=None, variant="default"):
    e = {"name": name, "track": track, "stage": stage, "mode": mode,
         "status": "DNF", "metrics": {}, "id": rid, "slug": slug, "variant": variant}
    if combo:
        e["combo"] = combo
    return e


def flush_index(runs):
    """Merge the current runs into results/index.json (replace matching ids) and write immediately,
    so a long run's progress is visible on the leaderboard as it goes."""
    idx = ROOT / "results" / "index.json"
    idx.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(idx.read_text()).get("runs", []) if idx.exists() else []
    ids = {r["id"] for r in runs}
    merged = [r for r in existing if r.get("id") not in ids] + runs
    idx.write_text(json.dumps({"generated": None, "runs": merged}, indent=2) + "\n")
    return len(merged)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/sim/dev")
    ap.add_argument("--mode", choices=["isolated", "composed", "both"], default="both")
    ap.add_argument("--runner", choices=["local", "docker", "apptainer"], default="local",
                    help="local runs run.sh directly; docker/apptainer run each submission's image")
    ap.add_argument("--only", default=None, help="restrict isolated evaluation to this slug")
    ap.add_argument("--focus", default=None,
                    help="incremental: isolated for this slug, and every composed combo that includes "
                         "it (its own stage is pinned to it; complementary stages stay full)")
    ap.add_argument("--include", default=None, help="comma-separated slugs to restrict the run to")
    ap.add_argument("--exclude", default=None,
                    help="comma-separated slugs to DROP from the run (isolated + composed). Used by "
                         "score.yml's full re-run so the hosted shards skip methods pinned to the "
                         "self-hosted runner; those run as separate --focus jobs on that runner.")
    ap.add_argument("--shard", default=None, metavar="i/n",
                    help="run only shard i of n disjoint shards (0-indexed), for parallel scoring "
                         "across jobs. Composed work is split by (field-map, bfr) COLUMN so each "
                         "column's bfr localfield is computed in exactly one shard; isolated runs "
                         "and spans are split round-robin. Union of all n shards == a full run.")
    ap.add_argument("--track", default="sim")
    ap.add_argument("--runs-out", type=Path, default=None,
                    help="write ONLY the runs produced by this invocation to this JSON file, instead "
                         "of merging into results/index.json. For sharded scoring: each shard writes "
                         "its own runs; a merge step combines them into index.json.")
    ap.add_argument("--work", type=Path, default=ROOT / ".work")
    ap.add_argument("--emit-volumes", action="store_true",
                    help="write recon/truth/error NIfTIs per run under results/<id>/ for the web viewer")
    ap.add_argument("--fail-on-dnf", action="store_true",
                    help="exit non-zero if any run in scope DNF'd (a submission that couldn't run or "
                         "produce a scorable artifact). Used by evaluate.yml so a broken run.sh / crash "
                         "surfaces as a red check instead of a silently-swallowed DNF.")
    args = ap.parse_args()

    global EMIT_VOLUMES
    EMIT_VOLUMES = args.emit_volumes

    # --shard i/n : this job runs shard i of n. `_owns(index)` is a deterministic round-robin over a
    # stable ordering, so the n shards partition the work with no overlap and no gaps.
    shard_i, shard_n = (None, None)
    if args.shard:
        shard_i, shard_n = (int(x) for x in args.shard.split("/"))
        if not (0 <= shard_i < shard_n):
            raise SystemExit(f"--shard i/n needs 0 <= i < n, got {args.shard}")
    def _owns(index):
        return shard_n is None or index % shard_n == shard_i

    inputs, gt = args.dataset / "inputs", args.dataset / "groundtruth"
    mask, params = inputs / "mask.nii.gz", inputs / "params.json"
    # GT-backed source map: inputs for raw artifacts, groundtruth for stage boundaries.
    gt_sources = {
        "phase": inputs / "phase.nii.gz", "magnitude": inputs / "magnitude.nii.gz",
        "mask": mask, "params": params,
        "totalfield": gt / "totalfield.nii.gz", "localfield": gt / "localfield.nii.gz",
        "chimap": gt / "chimap.nii.gz",
    }
    algos = discover_algorithms()
    if args.include:
        keep = set(args.include.split(","))
        algos = [a for a in algos if a["slug"] in keep]
    if args.exclude:
        drop = set(args.exclude.split(","))
        algos = [a for a in algos if a["slug"] not in drop]
    print(f"discovered {len(algos)} submissions:",
          ", ".join(f"{a['slug']}[{a['stage']}]" for a in algos))
    runs: list[dict] = []
    args.work.mkdir(parents=True, exist_ok=True)

    # Image resolution (pull, network allowed) is owned by the `qsm-ci` CLI now — each run_algo call
    # in docker mode shells out to `qsm-ci run …`, which pulls the submission's prebuilt image. A
    # submission whose image can't be pulled DNFs at run time (per-run, doesn't sink the batch).
    iso_target = args.focus or args.only  # isolated runs only this slug when set

    # -------- isolated (independent runs -> parallel) --------
    if args.mode in ("isolated", "both"):
        iso_algos = [a for a in algos if not (iso_target and a["slug"] != iso_target)]

        # Each algorithm runs at its defaults; one that declares `tuned:` params also runs a second
        # "tuned" variant (same isolated inputs, overrides applied) so the leaderboard's default/tuned
        # toggle has both. Variants are independent runs — expand them into the parallel pool.
        def iso_variants(a):
            vs = [("default", None)]
            if a.get("tuned"):
                vs.append(("tuned", a["tuned"]))
            return [(a, name, ov) for name, ov in vs]

        def do_isolated(task):
            a, variant, overrides = task
            sfx = "" if variant == "default" else "-tuned"
            idir = args.work / f"iso_{a['slug']}{sfx}_in"
            odir = args.work / f"iso_{a['slug']}{sfx}_out"
            try:
                prepare_input(a["consumes"], gt_sources, idir)
                rt = run_algo(a, idir, odir, args.runner, overrides)
                out = []
                for art in a["produces"]:
                    meta = {"id": f"{a['slug']}-iso{sfx}", "slug": a["slug"], "name": a["slug"],
                            "stage": a["stage"], "mode": "isolated", "track": args.track, "runtime": rt,
                            "variant": variant}
                    if overrides:
                        meta["params"] = overrides
                    r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                              args.work / f"iso_{a['slug']}{sfx}.json", meta)
                    out.append(r)
                    m = r["metrics"]
                    if r.get("status") == "DNF":
                        print(f"  isolated  {a['slug']:<16} {variant:<8} {art:<11} DNF ({r.get('dnf_reason','')})")
                    else:
                        print(f"  isolated  {a['slug']:<16} {variant:<8} {art:<11} "
                              f"xsim={_fmt(m.get('xsim'))} nrmse={_fmt(m.get('nrmse'), '.2f')}%")
                return out
            except Exception as e:  # DNF — record and continue
                print(f"  isolated  {a['slug']:<16} {variant:<8} DNF ({e})")
                return [dnf(f"{a['slug']}-iso{sfx}", a["slug"], a["slug"], a["stage"], "isolated",
                            args.track, variant=variant)]

        iso_tasks = [t for a in iso_algos for t in iso_variants(a)]
        iso_tasks = [t for idx, t in enumerate(iso_tasks) if _owns(idx)]  # --shard: round-robin
        for out in _pmap(iso_tasks, do_isolated):
            runs.extend(out)
        if not args.runs_out:
            flush_index(runs)

    # -------- composed: (field-mapping) x bfr x dipole, chaining real outputs --------
    # Dependency order is fieldmap -> bfr -> dipole, so each stage is a barrier; but every
    # combo within a stage is independent, so each stage fans out over the pool.
    if args.mode in ("composed", "both"):
        fmap = [a for a in algos if "totalfield" in a["produces"]]
        bfr = [a for a in algos if "localfield" in a["produces"]]
        dipole = [a for a in algos if a["stage"] == "dipole"]
        spans = [a for a in algos if "chimap" in a["produces"] and a["stage"] != "dipole"]

        if args.focus:  # pin the focus's own stage to it; every combo that includes it still runs
            f = next((a for a in algos if a["slug"] == args.focus), None)
            if f is None:
                fmap, bfr, dipole, spans = [], [], [], []
            elif f["stage"] == "dipole":
                dipole, spans = [f], []
            elif "localfield" in f["produces"]:      # a bfr (or unwrap+bfr) — this bfr × all dipoles
                bfr, spans = [f], []
            elif "totalfield" in f["produces"]:      # a field-mapping — this map through the matrix
                fmap, spans = [f], []
            else:                                     # a bfr+dipole / end-to-end span — run it alone
                fmap, bfr, dipole, spans = [], [], [], [f]

        # --shard: own each composed COLUMN = (totalfield-source, bfr) via round-robin over a stable
        # ordering. A column's bfr localfield is computed in exactly one shard (no cross-shard bfr
        # recomputation); a field-map runs only in shards that own a column consuming it.
        fm_keys = ["gt"] + sorted(f["slug"] for f in fmap)
        col_owner = {(tfk, bs): idx for idx, (tfk, bs)
                     in enumerate((tfk, b["slug"]) for tfk in fm_keys for b in sorted(bfr, key=lambda x: x["slug"]))}
        owns_col = lambda tfk, bs: _owns(col_owner.get((tfk, bs), 0))
        if shard_n is not None:
            needed_fm = {tfk for (tfk, bs) in col_owner if tfk != "gt" and owns_col(tfk, bs)}
            fmap = [f for f in fmap if f["slug"] in needed_fm]
            spans = [s for idx, s in enumerate(sorted(spans, key=lambda x: x["slug"])) if _owns(idx)]

        # Stage 1 — totalfield sources: the ground-truth field ("gt") plus each field-mapping
        # submission's output (run on raw inputs), so the matrix can start from raw phase.
        # Each source is (totalfield, valid-region mask, cumulative runtime s) so downstream stages
        # inherit any erosion and can accumulate the full pipeline's wall-clock time. The ground-truth
        # field costs nothing to "produce", so its runtime is 0.
        tf_sources: dict[str, tuple] = {"gt": (gt / ARTIFACT_FILE["totalfield"], mask, 0.0)}

        def do_fieldmap(f):
            idir, odir = args.work / f"cmp_fm_{f['slug']}_in", args.work / f"cmp_fm_{f['slug']}_out"
            try:
                prepare_input(f["consumes"], gt_sources, idir)
                fm_rt = run_algo(f, idir, odir, args.runner)
                tf = odir / "totalfield.nii.gz"
                # A field-mapping method may erode (e.g. Laplacian unwrapping) — carry its valid region.
                fm_mask = _valid_mask(tf, mask, odir / "validmask.nii.gz")
                return (f["slug"], tf, fm_mask, fm_rt)
            except Exception as e:
                print(f"  composed  fieldmap {f['slug']} DNF ({e}) — skipping its pipelines")
                return None

        for res in _pmap(fmap, do_fieldmap):
            if res:
                tf_sources[res[0]] = (res[1], res[2], res[3])

        # Stage 2 — bfr: localfield for each (totalfield source, bfr), keyed (tfk, bfr slug).
        # Each entry caches (localfield, valid-region mask, cumulative runtime s) so the dipole
        # inherits any erosion and the upstream field-mapping + BFR wall-clock time.
        lf_cache: dict[tuple, tuple] = {}

        def do_bfr(task):
            tfk, tfp, tf_mask, fm_rt, b = task
            idir, odir = args.work / f"cmp_{tfk}_{b['slug']}_in", args.work / f"cmp_{tfk}_{b['slug']}_out"
            try:
                # Run within the incoming valid region (not the full mask) so a field-mapping erosion
                # already narrows the boundary before the BFR erodes further.
                src = dict(gt_sources); src["totalfield"] = tfp; src["mask"] = tf_mask
                prepare_input(b["consumes"], src, idir)
                bfr_rt = run_algo(b, idir, odir, args.runner)
                lf = odir / "localfield.nii.gz"
                bfr_mask = _valid_mask(lf, tf_mask, odir / "validmask.nii.gz")
                return ((tfk, b["slug"]), (lf, bfr_mask, fm_rt + bfr_rt))
            except Exception as e:
                print(f"  composed  {tfk}+{b['slug']} bfr DNF ({e})")
                return None

        bfr_tasks = [(tfk, tfp, tf_mask, fm_rt, b) for tfk, (tfp, tf_mask, fm_rt) in tf_sources.items()
                     for b in bfr if owns_col(tfk, b["slug"])]  # --shard: only this shard's columns
        for res in _pmap(bfr_tasks, do_bfr):
            if res:
                lf_cache[res[0]] = res[1]

        # Stage 3 — dipole: invert each cached localfield with every dipole method.
        def do_dipole(task):
            tfk, b, d = task
            combo = f"{b['slug']}+{d['slug']}" if tfk == "gt" else f"{tfk}+{b['slug']}+{d['slug']}"
            cid = f"{tfk}~{b['slug']}~{d['slug']}-cmp"
            cinfo = {"field_mapping": tfk, "bfr": b["slug"], "dipole": d["slug"]}
            try:
                lf, bfr_mask, upstream_rt = lf_cache[(tfk, b["slug"])]
                # Invert within the BFR's eroded region — not the original full mask — so the dipole
                # never deconvolves a zero-field rim into a blurry boundary.
                src = dict(gt_sources); src["localfield"] = lf; src["mask"] = bfr_mask
                idir, odir = args.work / f"cmp_{cid}_in", args.work / f"cmp_{cid}_out"
                prepare_input(d["consumes"], src, idir)
                rt = run_algo(d, idir, odir, args.runner)
                # runtime_s is the whole pipeline's wall-clock: field-mapping + BFR (upstream_rt) + dipole.
                meta = {"id": cid, "slug": combo, "name": combo,
                        "stage": "bfr+dipole" if tfk == "gt" else "field-mapping+bfr+dipole",
                        "mode": "composed", "track": args.track, "runtime": upstream_rt + rt, "combo": cinfo}
                r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                          args.work / f"cmp_{cid}.json", meta)
                m = r["metrics"]
                if r.get("status") == "DNF":
                    print(f"  composed  {combo:<34} DNF ({r.get('dnf_reason','')})")
                else:
                    print(f"  composed  {combo:<34} chimap xsim={_fmt(m.get('xsim'))} "
                          f"nrmse_dt={_fmt(m.get('nrmse_detrend'), '.2f')}%")
                return r
            except Exception as e:
                print(f"  composed  {combo:<34} DNF ({e})")
                return dnf(cid, combo, combo, "field-mapping+bfr+dipole", "composed", args.track, cinfo)

        dip_tasks = [(tfk, b, d) for tfk in tf_sources for b in bfr
                     if (tfk, b["slug"]) in lf_cache for d in dipole]
        for r in _pmap(dip_tasks, do_dipole):
            runs.append(r)
        if not args.runs_out:
            flush_index(runs)

        # Stage 4 — spans (bfr+dipole / end-to-end submissions), independent.
        def do_span(s):
            idir, odir = args.work / f"cmp_{s['slug']}_in", args.work / f"cmp_{s['slug']}_out"
            try:
                prepare_input(s["consumes"], gt_sources, idir)
                rt = run_algo(s, idir, odir, args.runner)
                meta = {"id": f"{s['slug']}-cmp", "slug": s["slug"], "name": s["slug"],
                        "stage": s["stage"], "mode": "composed", "track": args.track, "runtime": rt}
                return score(odir / "chimap.nii.gz", "chimap", gt, mask,
                             args.work / f"cmp_{s['slug']}.json", meta)
            except Exception as e:
                print(f"  composed  {s['slug']:<28} DNF ({e})")
                return dnf(f"{s['slug']}-cmp", s["slug"], s["slug"], s["stage"], "composed", args.track)

        for r in _pmap(spans, do_span):
            runs.append(r)

    if args.runs_out:
        args.runs_out.parent.mkdir(parents=True, exist_ok=True)
        args.runs_out.write_text(json.dumps(runs, indent=2) + "\n")
        print(f"\nwrote {len(runs)} runs to {args.runs_out} (shard output; not merged into index.json)")
    else:
        total = flush_index(runs)
        print(f"\nmerged {len(runs)} runs into results/index.json ({total} total)")

    if args.fail_on_dnf:
        dnfs = [r for r in runs if r.get("status") == "DNF"]
        if dnfs:
            print(f"\n::error::{len(dnfs)} run(s) DNF'd: "
                  f"{', '.join(sorted({r['slug'] for r in dnfs}))}")
            sys.exit(1)


if __name__ == "__main__":
    main()
