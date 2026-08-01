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
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"

# Single source of truth for the stage graph + artifact tables (checked vs stages.yml by
# tests/test_stages_sync.py) — previously a third divergent copy lived here. Put the repo root on
# sys.path so `qsm_ci` resolves straight from the checkout even when the package isn't pip-installed
# in the interpreter running this script (CI installs it; a bare `python scripts/pipeline.py` may
# not). qsm_ci.stages is pure literals — no yaml/heavy deps.
sys.path.insert(0, str(ROOT))
from qsm_ci.stages import STAGES, ARTIFACT_FILE, ARTIFACT_KIND  # noqa: E402
# Shared scoring/sweep primitives (also used by scripts/sweep.py + combo_sweep.py) — one home for the
# `qsm-ci run` argv builder, the GT source map, the --shard partition, and the qsm_eval argv, so the
# scorer and the sweeps can't drift. Pure literals/argv assembly — no heavy deps at import.
from qsm_ci.scoring import (  # noqa: E402
    cli_run_argv, gt_sources as _gt_sources, parse_shard, shard_owns, shard_partition, eval_argv,
)

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

# Stage graph / artifact tables: STAGES, ARTIFACT_FILE, ARTIFACT_KIND are imported once from
# qsm_ci.stages (top of file) — single source of truth, checked against stages.yml by
# tests/test_stages_sync.py. Previously duplicated here, which was a third copy free to drift.

# Emitting per-run recon/truth/error NIfTIs (for the web viewer) is threaded explicitly as an
# `emit_volumes_on` boolean parameter through score()/_emit_composed_resources()/run_isolated()/
# run_composed() — main() reads it from --emit-volumes and passes it down. No module-global state.


def emit_volumes(run_id, recon, truth, mask=None, resources=None, suffix=""):
    """Write recon / truth / error volumes under results/<run_id>/ for the NiiVue viewer.

    The error map is the signed difference recon - truth, zeroed outside the raw brain mask so the
    background stays clean (the viewer shows it with a diverging red↔blue colormap). `suffix` names a
    second volume set on the same run — χ-separation uses "-dia" for its χ− source so the viewer's
    χ+/χ− toggle can load recon-dia.nii.gz etc. alongside the plain χ+ set."""
    import nibabel as nib
    d = ROOT / "results" / run_id
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(recon, d / f"recon{suffix}.nii.gz")
    shutil.copy(truth, d / f"truth{suffix}.nii.gz")
    if resources is not None and Path(resources).exists():
        shutil.copy(resources, d / "resources.json")  # memory/CPU-over-time trace for the graph
    r, t = nib.load(str(recon)), nib.load(str(truth))
    err = (r.get_fdata() - t.get_fdata()).astype("float32")
    if mask is not None:
        err[nib.load(str(mask)).get_fdata() <= 0.5] = 0.0
    nib.save(nib.Nifti1Image(err, r.affine), str(d / f"error{suffix}.nii.gz"))


def _load_resources(path) -> "dict | None":
    """Read a stage's resources.json (as written by qsm_ci.runner._ResourceSampler), or None if it's
    missing/unreadable — a stage may legitimately produce no trace (a sub-2s run, or the local runner
    which doesn't sample), and that must never sink the composed run."""
    try:
        p = Path(path)
        if not p.exists():
            return None
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001 — profiling is best-effort
        return None


def concat_resources(stages: list) -> "dict | None":
    """Concatenate per-stage resource traces into one series for a composed run.

    `stages` is a list of `(name, resources_path, duration_s)` in EXECUTION ORDER — the field-mapping
    → BFR → dipole sequence, each with the same measured wall-time pipeline.py already sums for the
    composed run's `runtime_s`. Each stage's own resources.json (memory/CPU over time) is loaded and:

      - its `t[]` samples are offset by the cumulative wall-time of all PRIOR stages (their measured
        durations), so the combined timeline's span matches `runtime_s` and the graph lines up with
        the metrics/NiiVue image on the submission page;
      - `mem_bytes` / `cpu_cores` are concatenated in the same order;
      - `mem_peak_bytes` / `cpu_cores_max` are the max over all stages;
      - a `stages` field records each stage's `{name, t_start, t_end}` boundary (front-end may mark
        stage transitions; it can also ignore it).

    A stage with no samples (e.g. a <2s run, or none captured) contributes zero points but its
    duration still advances the offset, so later stages — and the total span — stay aligned with
    `runtime_s`. Returns None only when there are no stages at all."""
    if not stages:
        return None
    t_all: list = []
    mem_all: list = []
    cpu_all: list = []
    bounds: list = []
    peak = 0.0
    cpu_max = 0.0
    interval = None
    runner = None
    offset = 0.0
    for name, path, duration in stages:
        try:
            dur = float(duration)
        except (TypeError, ValueError):
            dur = 0.0
        data = _load_resources(path) or {}
        st = data.get("t") or []
        sm = data.get("mem_bytes") or []
        sc = data.get("cpu_cores") or []
        n = min(len(st), len(sm), len(sc))  # only keep aligned samples
        for i in range(n):
            t_all.append(round(offset + float(st[i]), 3))
            mem_all.append(sm[i])
            cpu_all.append(sc[i])
        if data.get("mem_peak_bytes"):
            peak = max(peak, float(data["mem_peak_bytes"]))
        elif sm:
            peak = max(peak, float(max(sm[:n] or sm)))
        if data.get("cpu_cores_max") is not None:
            cpu_max = max(cpu_max, float(data["cpu_cores_max"]))
        elif sc:
            cpu_max = max(cpu_max, float(max(sc[:n] or sc)))
        if interval is None and data.get("interval_s") is not None:
            interval = data["interval_s"]
        if runner is None and data.get("runner"):
            runner = data["runner"]
        bounds.append({"name": name, "t_start": round(offset, 3), "t_end": round(offset + dur, 3)})
        offset += dur
    return {
        "interval_s": interval if interval is not None else 1.0,
        "t": t_all,
        "mem_bytes": mem_all,
        "cpu_cores": cpu_all,
        "mem_peak_bytes": peak,
        "cpu_cores_max": cpu_max,
        # mean over the whole concatenated timeline (all stages), so composed runs summarise the same
        # way isolated ones do — see qsm_ci.resources for the interpretation.
        "cpu_cores_avg": (sum(cpu_all) / len(cpu_all)) if cpu_all else 0,
        "sampler": "docker-stats",
        "runner": runner or "docker",
        "stages": bounds,
        "composed": True,
    }


def _emit_composed_resources(run_id: str, stages: list, emit_volumes_on: bool) -> None:
    """Write the concatenated composed-run trace to results/<run_id>/resources.json, replacing the
    single-stage copy emit_volumes() left there. Only writes when emit_volumes_on is set (the same
    gate that produces the viewer volumes) and there's a real trace to write. Never raises into the
    run — a failed profile write must not fail the pipeline."""
    if not emit_volumes_on:
        return
    try:
        doc = concat_resources(stages)
        if not doc or not doc.get("t"):
            return  # no samples at all (e.g. every stage <2s, or the local runner) — leave as-is
        d = ROOT / "results" / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "resources.json").write_text(json.dumps(doc))
    except Exception:  # noqa: BLE001 — profiling is best-effort
        pass


def _yaml_scalar(v) -> str:
    """Render a parsed YAML scalar as the bare token the old regex captured (`\\S+`).

    The previous parser read `stage:`/`image:`/`tuned:`/list items straight out of the text as
    strings, so every consumer downstream expects a `str`. yaml.safe_load instead coerces `520`→int,
    `0.00015`→float, etc. Stringifying restores the old type/shape without a lossy re-parse — and for
    every value in the repo's ymls `str(safe_load(tok)) == tok` (ints, plain floats, and `NeM`
    exponents alike), so the tuned/optional/stage strings are byte-identical to the regex output."""
    return str(v)


def _tuned_overrides(doc: dict, dataset: str = "sim") -> dict:
    """Extract `{param: tuned_value}` for a dataset (`sim` / `invivo` / `chisep`) from a parsed
    algorithm.yml `parameters:` block — the settings optimised on that dataset (each parameter may
    carry a `tuned:` alongside its `default:`). `tuned` is either a per-dataset MAP
    (`tuned: {sim: .., invivo: .., chisep: ..}`) or a legacy SCALAR (which applies to the in-silico/sim
    dataset only). So sim keeps reading the existing scalar tunings, and a method only gets an
    in-vivo / chi-sep tuned variant once it declares `tuned.invivo` / `tuned.chisep`.

    Values are returned as strings (they flow into `overrides` -> config.json / `--set`, which expect
    the raw token). YAML handles the unindented list items (`- name:` at column 0, as the MATLAB ymls
    write them) that the old regex needed a special workaround for."""
    params = doc.get("parameters")
    if not isinstance(params, list):
        return {}
    out = {}
    for item in params:
        if not isinstance(item, dict) or "name" not in item or "tuned" not in item:
            continue
        t = item["tuned"]
        val = t.get(dataset) if isinstance(t, dict) else (t if dataset == "sim" else None)
        if val is None:
            continue
        out[_yaml_scalar(item["name"])] = _yaml_scalar(val)
    return out


def discover_algorithms(track: str = "sim") -> list[dict]:
    # `track` selects which dataset's tuned params each method carries: a chi-separation method is only
    # ever scored on the chisep dataset (→ "chisep"), otherwise the in-vivo run uses "invivo" and
    # everything else "sim". So the tuned variant a run expands is the one optimised on ITS dataset.
    algos = []
    # QSMCI_ALGORITHMS_DIR lets a harness test point discovery at a fixture method set (tests/methods)
    # instead of the real algorithms/ tree — so the orchestration (discover -> isolated/composed ->
    # score -> index) can be smoke-tested end-to-end on the local runner without any real container.
    algos_root = Path(os.environ.get("QSMCI_ALGORITHMS_DIR") or (ROOT / "algorithms"))
    for d in sorted(algos_root.glob("*/")):
        spec = d / "algorithm.yml"
        if d.name.startswith("_") or not spec.exists():
            continue
        try:
            doc = yaml.safe_load(spec.read_text())
        except yaml.YAMLError:
            # A malformed yaml the old regex parser might have limped past — skip rather than crash
            # the whole discovery, matching the old `if not stage: continue` graceful behaviour.
            continue
        if not isinstance(doc, dict) or doc.get("stage") is None:
            continue
        s = _yaml_scalar(doc["stage"])
        image = doc.get("image")
        # Mirror runner._consumes EXACTLY so the scorer mounts + passes only the flags `qsm-ci run`
        # accepts; otherwise it passes a flag the CLI rejects (e.g. --magnitude) and the run DNFs.
        # A method may NARROW its inputs (`inputs:` — the exact artifacts it reads, a subset of the
        # stage), or ADD optional extras (`optional_inputs:` — e.g. MEDI (dipole) uses magnitude for
        # edge weighting). `inputs:` wins; else stage baseline + optional extras.
        base = STAGES[s]["consumes"]
        explicit = doc.get("inputs")
        if isinstance(explicit, list):
            want = {_yaml_scalar(a) for a in explicit}
            consumes = [a for a in base if a in want]
        else:
            opt = doc.get("optional_inputs")
            optional = [_yaml_scalar(a) for a in opt] if isinstance(opt, list) else []
            consumes = base + [a for a in optional if a not in base]
        algos.append({
            "slug": d.name, "dir": d, "stage": s,
            "name": _yaml_scalar(doc.get("name")) if doc.get("name") is not None else d.name,
            "image": _yaml_scalar(image) if image is not None else None,
            "consumes": consumes, "produces": STAGES[s]["produces"],
            "tuned": _tuned_overrides(doc, "chisep" if s == "chi-separation"
                                      else ("invivo" if track == "invivo" else "sim")),
            # Optional per-method smoke-crop size (voxels): a slow per-voxel method (e.g. DECOMPOSE)
            # can shrink the --smoke gate's central box so the PR check stays fast; None = CLI default.
            "smoke_box": doc.get("smoke_box"),
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
        # Ask the CLI's container runner to trace this run's memory/CPU over time into the output dir
        # (resources.json); score()/emit_volumes() later copy it next to the viewer volumes.
        env = {**os.environ, "QSMCI_RESOURCES_OUT": str(output_dir / "resources.json")}
        subprocess.run(cli_run_argv(algo, input_dir, output_dir, ARTIFACT_FILE, runner, overrides),
                       check=True, env=env)
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


def score(recon: Path, artifact: str, gt_dir: Path, mask: Path, out_json: Path, meta: dict,
          emit_volumes_on: bool = False) -> dict:
    kind = ARTIFACT_KIND[artifact]
    raw_mask = mask  # the full brain mask, before erosion — used to mask the viewer's error map
    # Score only where the method actually produced a value (its non-zero support), so an eroded
    # rim isn't penalised as error — consistent with masking that rim out of the pipeline.
    mask = _valid_mask(recon, mask, out_json.parent / (out_json.stem + "_scoremask.nii.gz"))
    seg = gt_dir / "dseg.nii.gz"
    component = {"chi-para": "para", "chi-dia": "dia"}.get(artifact)  # χ-sep source for region metrics
    # The in-vivo (2016 challenge) dataset DOES ship a dseg, but it follows a different label scheme
    # (0–11) than the sim phantom's tissue/blood/DGM/calcification labels, so its region metrics would
    # be meaningless. Withhold the seg for that track → the scorer's no-seg chi branch (global
    # NRMSE/HFEN/correlation/XSIM only), which is exactly the in-vivo metric set.
    use_seg = kind in ("chi", "chisep") and seg.exists() and meta["track"] != "invivo"
    cmd = eval_argv(sys.executable, EVAL, recon, gt_dir / ARTIFACT_FILE[artifact], kind, mask,
                    artifact, out_json, stage=meta["stage"], name=meta["name"], track=meta["track"],
                    runtime=meta.get("runtime"),
                    seg=seg if use_seg else None,
                    component=component)
    subprocess.run(cmd, check=True)
    result = json.loads(out_json.read_text())
    # A scorable recon yields finite metrics; an all-NaN / empty output makes the scorer emit
    # null/NaN. Record that as a clear DNF (not a metric-less "ok" row, and without crashing the
    # caller's formatted print) so the failure is legible instead of a cryptic format-string error.
    primary = (result.get("metrics") or {}).get("xsim" if kind in ("chi", "chisep") else "nrmse")
    if _finite(primary):
        result["status"] = "ok"
    else:
        result["status"] = "DNF"
        result["dnf_reason"] = "non-finite output (unscorable)"
    result.update({k: meta[k] for k in ("id", "slug", "mode", "variant", "params") if k in meta})
    if "combo" in meta:
        result["combo"] = meta["combo"]
    if emit_volumes_on and "id" in meta:
        # The container runner (docker/podman path) writes resources.json beside the recon in the
        # run's output dir; carry it into results/<id>/ so the web viewer can graph it.
        res = recon.parent / "resources.json"
        emit_volumes(meta["id"], recon, gt_dir / ARTIFACT_FILE[artifact], raw_mask,
                     resources=res if res.exists() else None)
    return result


def id_suffix(track: str) -> str:
    """Run-id namespace for a track. The QSM sim track keeps the historical bare ids (`<slug>-iso`,
    `<slug>-cmp`, …) so a re-score overwrites the existing leaderboard entry in place; every other
    track (currently just `invivo`) appends `-<track>` so its runs live in a disjoint id space and
    never collide with the sim entries in results/index.json."""
    return "" if track == "sim" else f"-{track}"


# Secondary reference for the in-vivo track: the STI χ33 map is scored by re-running the SAME dipole
# recon through the scorer against groundtruth/chimap-sti.nii.gz, and its metrics are merged into the
# primary (COSMOS) run under a `_sti` suffix. There is no second recon — just a second scoring pass.
STI_REFERENCE = "chimap-sti.nii.gz"


def score_secondary(recon: Path, gt_dir: Path, mask: Path, out_json: Path, meta: dict,
                    ref_file: str, suffix: str) -> dict:
    """Score `recon` against a SECONDARY ground-truth reference (`gt_dir/ref_file`) and return its
    metrics keyed with `suffix` appended (e.g. `nrmse` -> `nrmse_sti`). Used by the in-vivo track to
    add the STI χ33 reference alongside the primary COSMOS reference without a second recon. Returns
    {} if the reference file is absent (secondary is optional — primary behaviour is untouched)."""
    ref = gt_dir / ref_file
    if not ref.exists():
        return {}
    kind = ARTIFACT_KIND["chimap"]
    smask = _valid_mask(recon, mask, out_json.parent / (out_json.stem + "_scoremask.nii.gz"))
    cmd = eval_argv(sys.executable, EVAL, recon, ref, kind, smask, "chimap", out_json,
                    stage=meta["stage"], name=meta["name"], track=meta["track"],
                    runtime=meta.get("runtime"))
    subprocess.run(cmd, check=True)
    metrics = (json.loads(out_json.read_text()).get("metrics") or {})
    return {f"{k}{suffix}": v for k, v in metrics.items()}


def dnf(rid, slug, name, stage, mode, track, combo=None, variant="default"):
    e = {"name": name, "track": track, "stage": stage, "mode": mode,
         "status": "DNF", "metrics": {}, "id": rid, "slug": slug, "variant": variant}
    if combo:
        e["combo"] = combo
    return e


def _stamp_resource_summary(run):
    """Copy the resource summary — peak memory, avg + peak CPU — from a run's resources.json onto the
    run row, next to runtime_s, so the leaderboard and findings figures read it directly instead of
    fetching the full time-series. Best-effort: a run with no trace (a sub-2s run, or the local runner
    which doesn't sample) simply leaves the fields absent, and the figure drops it from those axes."""
    try:
        p = ROOT / "results" / run["id"] / "resources.json"
        if not p.exists():
            return
        d = json.loads(p.read_text())
    except Exception:  # noqa: BLE001 — profiling is best-effort; never sink a run over it
        return
    for k in ("mem_peak_bytes", "cpu_cores_avg", "cpu_cores_max"):
        if d.get(k):
            run[k] = d[k]


def flush_index(runs):
    """Merge the current runs into results/index.json (replace matching ids) and write immediately,
    so a long run's progress is visible on the leaderboard as it goes."""
    idx = ROOT / "results" / "index.json"
    idx.parent.mkdir(parents=True, exist_ok=True)
    for r in runs:
        _stamp_resource_summary(r)
    existing = json.loads(idx.read_text()).get("runs", []) if idx.exists() else []
    ids = {r["id"] for r in runs}
    merged = [r for r in existing if r.get("id") not in ids] + runs
    idx.write_text(json.dumps({"generated": None, "runs": merged}, indent=2) + "\n")
    return len(merged)


# ---------------------------------------------------------------------------------------------------
# Isolated evaluation: each stage/span fed its GROUND-TRUTH consumed artifacts, scored vs GT. Each
# (algorithm, variant) is an independent run, so they fan out over the pool (_pmap). Hoisted from
# main()'s nested closures — everything they used to capture (args, the GT source map, the GT dir,
# the raw mask, the track, the emit-volumes flag) is now passed explicitly.
# ---------------------------------------------------------------------------------------------------

def iso_variants(a: dict) -> list:
    """Expand an algorithm into its isolated runs: always its defaults, plus a second "tuned" variant
    when it declares `tuned:` params (same isolated inputs, overrides applied) so the leaderboard's
    default/tuned toggle has both. Each element is (algo, variant_name, overrides_or_None)."""
    vs = [("default", None)]
    if a.get("tuned"):
        vs.append(("tuned", a["tuned"]))
    return [(a, name, ov) for name, ov in vs]


# χ-separation folds its two produced source maps into one leaderboard row: χ+ → para_*, χ− → dia_*.
CHISEP_PREFIX = {"chi-para": "para", "chi-dia": "dia"}


def _chisep_leakage(odir, gt, mask) -> "dict | None":
    """Whole-brain cross-source leakage for a χ-separation run: {para_leak, dia_leak}.

    Regress each reconstructed source on BOTH ground-truth sources (recon ≈ a·GT_same + b·GT_other + c)
    and take the slope `b` on the WRONG source — the fraction of the other source that bleeds into this
    map (0 = clean separation). Because it controls for the correct source, it isolates true χ+↔χ−
    contamination, unlike xSIM/NRMSE which are dominated by the shared R2'/2Dr common mode. Needs both
    GT sources, so it's computed here rather than per-component. Returns None if a map can't be read."""
    import numpy as np
    import nibabel as nib
    L = lambda p: np.asarray(nib.load(str(p)).get_fdata(), np.float64)
    try:
        rp, rd = L(odir / ARTIFACT_FILE["chi-para"]), L(odir / ARTIFACT_FILE["chi-dia"])
        gp, gd = L(gt / ARTIFACT_FILE["chi-para"]), L(gt / ARTIFACT_FILE["chi-dia"])
        m = L(mask) > 0.5
    except Exception:  # noqa: BLE001 — a missing/unreadable map just means "no leakage number"
        return None
    def slope(recon, same, other):
        A = np.c_[same[m], other[m], np.ones(int(m.sum()))]
        return float(np.linalg.lstsq(A, recon[m], rcond=None)[0][1])
    return {"para_leak": slope(rp, gp, gd),   # χ− (diamagnetic) bleeding INTO the χ+ map
            "dia_leak":  slope(rd, gd, gp)}   # χ+ (paramagnetic) bleeding INTO the χ− map


def _score_chisep(a, sfx, variant, overrides, odir, gt, mask, rt, args):
    """Score a χ-separation run's two source maps (χ+, χ−) and fold them into ONE leaderboard row with
    para_*/dia_* prefixed metrics and domain='chisep' — the chi-sep leaderboard shows one row per
    method with χ+ vs χ− columns, not two separate rows. A DNF in either component marks the row DNF.

    Metrics per source: xsim/nrmse/correlation, region leakage (dia_iron_leak = mean |χ−| in the
    iron/DGM+vein regions where χ− should be ~0; para_calc_leak = mean |χ+| in calcification), and the
    whole-brain regression leakage (para_leak / dia_leak) from _chisep_leakage."""
    rid = f"{a['slug']}-iso{sfx}"
    row = {"id": rid, "slug": a["slug"], "name": a.get("name", a["slug"]), "stage": a["stage"], "mode": "isolated",
           "track": args.track, "runtime_s": rt, "variant": variant, "domain": "chisep",
           "kind": "chisep", "metrics": {}, "status": "ok"}
    if overrides:
        row["params"] = overrides
    for art in a["produces"]:
        pfx = CHISEP_PREFIX.get(art, art)
        meta = {"id": f"{rid}-{pfx}", "slug": a["slug"], "name": a["slug"], "stage": a["stage"],
                "mode": "isolated", "track": args.track, "runtime": rt, "variant": variant}
        # emit_volumes off: the two components would collide on one id; chi-sep viewer volumes are a
        # later feature. We only need each component's metrics here.
        r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                  args.work / f"iso_{a['slug']}{sfx}_{pfx}.json", meta, emit_volumes_on=False)
        for k, v in (r.get("metrics") or {}).items():
            row["metrics"][f"{pfx}_{k}"] = v
        if r.get("status") == "DNF":
            row["status"], row["dnf_reason"] = "DNF", r.get("dnf_reason", "")
        m = r.get("metrics") or {}
        shown = ("DNF" if r.get("status") == "DNF"
                 else f"xsim={_fmt(m.get('xsim'))} nrmse={_fmt(m.get('nrmse'), '.2f')}%")
        print(f"  isolated  {a['slug']:<16} {variant:<8} {art:<11} {shown}")
    if row["status"] != "DNF":  # whole-brain χ+↔χ− leakage (needs both GT + both recon maps)
        lk = _chisep_leakage(odir, gt, mask)
        if lk:
            row["metrics"].update(lk)
            print(f"  isolated  {a['slug']:<16} {variant:<8} {'leakage':<11} "
                  f"para_leak={_fmt(lk['para_leak'])} dia_leak={_fmt(lk['dia_leak'])}")
    # Viewer volumes: emit both sources under the run id (results/<id>/) — χ+ as the plain set and χ−
    # with a "-dia" suffix, so the detail viewer's χ+/χ− toggle can load either. The container runner
    # writes one resources.json (memory/CPU-over-time) beside the outputs for the whole run; carry it
    # on the χ+ set so the detail page graphs CPU/RAM for χ-sep methods too, like the QSM ones.
    if args.emit_volumes:
        res = odir / "resources.json"
        emit_volumes(rid, odir / ARTIFACT_FILE["chi-para"], gt / ARTIFACT_FILE["chi-para"], mask,
                     resources=res if res.exists() else None)
        emit_volumes(rid, odir / ARTIFACT_FILE["chi-dia"], gt / ARTIFACT_FILE["chi-dia"], mask, suffix="-dia")
    return row


def _smoke_crop(idir, consumes, box):
    """Crop each spatial input to a central box for a --smoke run (compute reduction): the method only
    has to RUN and emit a valid output, not score, so fewer voxels = a much faster iterative run while
    fully-convolutional networks just pad back up. Voxel resolution and the echo dim are preserved."""
    import nibabel as nib
    import numpy as np
    for art in consumes:
        if art == "params":
            continue
        f = idir / ARTIFACT_FILE[art]
        if not f.exists():
            continue
        im = nib.load(str(f))
        d = np.asarray(im.dataobj)
        sl = tuple(slice((n - box) // 2, (n - box) // 2 + box) if n > box else slice(None)
                   for n in d.shape[:3]) + tuple(slice(None) for _ in d.shape[3:])
        nib.save(nib.Nifti1Image(d[sl], im.affine, im.header), str(f))


def _smoke_check(a, sfx, variant, odir, rt, args):
    """--smoke gate: the method ran — did it emit each produced artifact as a valid (present, correctly
    shaped, finite, non-empty) volume? No scoring; a crash / missing / empty / non-finite output is a
    DNF that fails the check. This is what --smoke swaps in for score(): prove it runs, cheaply."""
    import nibabel as nib
    import numpy as np
    rid = f"{a['slug']}-iso{sfx}"
    row = {"id": rid, "slug": a["slug"], "name": a.get("name", a["slug"]), "stage": a["stage"],
           "mode": "isolated", "track": args.track, "runtime_s": rt, "variant": variant,
           "metrics": {}, "status": "ok", "smoke": True}
    if a["stage"] == "chi-separation":
        row["domain"] = "chisep"
    for art in a["produces"]:
        f = odir / ARTIFACT_FILE[art]
        if not f.exists():
            reason = "not written"
        else:
            d = np.asarray(nib.load(str(f)).dataobj, dtype="float32")
            reason = "empty / non-finite" if (not np.isfinite(d).any() or not np.any(d != 0)) else None
        print(f"  smoke     {a['slug']:<16} {variant:<8} {art:<11} {'ok' if reason is None else 'DNF (' + reason + ')'}")
        if reason:
            row["status"] = "DNF"
            row["dnf_reason"] = f"{art}: {reason}"
    return row


def do_isolated(task, args, gt_sources, gt, mask):
    """Run + score one isolated (algorithm, variant) task. Returns a list of result rows (one per
    produced artifact — χ-separation folds its two into one), or a single DNF row on any failure —
    never raises, so _pmap can't be sunk."""
    a, variant, overrides = task
    sfx = "" if variant == "default" else "-tuned"          # variant suffix (work paths)
    idsfx = sfx + id_suffix(args.track)                     # + track namespace (run ids)
    idir = args.work / f"iso_{a['slug']}{idsfx}_in"
    odir = args.work / f"iso_{a['slug']}{idsfx}_out"
    try:
        prepare_input(a["consumes"], gt_sources, idir)
        if args.smoke:
            _smoke_crop(idir, a["consumes"], a.get("smoke_box") or args.smoke_box)
        rt = run_algo(a, idir, odir, args.runner, overrides)
        prods = a["produces"]
        if args.smoke:  # smoke: prove it runs + emits a valid output, don't score
            return [_smoke_check(a, idsfx, variant, odir, rt, args)]
        if len(prods) > 1 and all(ARTIFACT_KIND.get(p) == "chisep" for p in prods):
            return [_score_chisep(a, idsfx, variant, overrides, odir, gt, mask, rt, args)]
        out = []
        for art in prods:
            meta = {"id": f"{a['slug']}-iso{idsfx}", "slug": a["slug"], "name": a.get("name", a["slug"]),
                    "stage": a["stage"], "mode": "isolated", "track": args.track, "runtime": rt,
                    "variant": variant}
            if overrides:
                meta["params"] = overrides
            r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                      args.work / f"iso_{a['slug']}{idsfx}.json", meta, args.emit_volumes)
            # In-vivo track: score the SAME chimap against the secondary STI χ33 reference too, and
            # merge its metrics under a `_sti` suffix (nrmse_sti, xsim_sti, …). COSMOS keeps the
            # unsuffixed keys. Skipped silently if chimap-sti.nii.gz isn't shipped (sim untouched).
            if args.track == "invivo" and art == "chimap" and r.get("status") != "DNF":
                sti = score_secondary(odir / ARTIFACT_FILE[art], gt, mask,
                                      args.work / f"iso_{a['slug']}{idsfx}_sti.json", meta,
                                      STI_REFERENCE, "_sti")
                r.setdefault("metrics", {}).update(sti)
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
        return [dnf(f"{a['slug']}-iso{idsfx}", a["slug"], a["slug"], a["stage"], "isolated",
                    args.track, variant=variant)]


def run_isolated(args, algos, gt_sources, gt, mask, iso_target, runs: list) -> None:
    """Isolated (independent runs -> parallel). Restricts to `iso_target` when set, expands each
    algorithm into its default/tuned variants, applies the --shard round-robin, runs them over the
    pool, appends the rows to `runs`, and flushes the index unless writing a shard file."""
    iso_algos = [a for a in algos if not (iso_target and a["slug"] != iso_target)]
    iso_tasks = [t for a in iso_algos for t in iso_variants(a)]
    iso_tasks = shard_partition(iso_tasks, args.shard)  # --shard: round-robin over a stable order
    for out in _pmap(iso_tasks, lambda task: do_isolated(task, args, gt_sources, gt, mask)):
        runs.extend(out)
    if not args.runs_out:
        flush_index(runs)


# ---------------------------------------------------------------------------------------------------
# Composed evaluation: (field-mapping) x bfr x dipole, chaining real outputs, plus spans. Dependency
# order is fieldmap -> bfr -> dipole, so each stage is a barrier; every combo within a stage is
# independent, so each stage fans out over the pool. bfr outputs are cached and reused across dipole
# methods (the N×M matrix). Hoisted from main()'s nested closures — everything they captured (args,
# the GT source map, the GT dir, the raw mask, the caches) is now passed explicitly.
# ---------------------------------------------------------------------------------------------------

def do_fieldmap(f, args, gt_sources, mask):
    """Run one field-mapping submission on raw inputs, returning
    (slug, totalfield, valid-mask, runtime, trace) or None on DNF."""
    idir, odir = args.work / f"cmp_fm_{f['slug']}_in", args.work / f"cmp_fm_{f['slug']}_out"
    try:
        prepare_input(f["consumes"], gt_sources, idir)
        fm_rt = run_algo(f, idir, odir, args.runner)
        tf = odir / "totalfield.nii.gz"
        # A field-mapping method may erode (e.g. Laplacian unwrapping) — carry its valid region.
        fm_mask = _valid_mask(tf, mask, odir / "validmask.nii.gz")
        trace = [(f"field-mapping:{f['slug']}", odir / "resources.json", fm_rt)]
        return (f["slug"], tf, fm_mask, fm_rt, trace)
    except Exception as e:
        print(f"  composed  fieldmap {f['slug']} DNF ({e}) — skipping its pipelines")
        return None


def do_bfr(task, args, gt_sources):
    """Run one (totalfield source, bfr) BFR within the incoming valid region, returning
    ((tfk, bfr slug), (localfield, valid-mask, cumulative runtime, trace)) or None on DNF."""
    tfk, tfp, tf_mask, fm_rt, fm_trace, b = task
    idir, odir = args.work / f"cmp_{tfk}_{b['slug']}_in", args.work / f"cmp_{tfk}_{b['slug']}_out"
    try:
        # Run within the incoming valid region (not the full mask) so a field-mapping erosion
        # already narrows the boundary before the BFR erodes further.
        src = dict(gt_sources); src["totalfield"] = tfp; src["mask"] = tf_mask
        prepare_input(b["consumes"], src, idir)
        bfr_rt = run_algo(b, idir, odir, args.runner)
        lf = odir / "localfield.nii.gz"
        bfr_mask = _valid_mask(lf, tf_mask, odir / "validmask.nii.gz")
        trace = fm_trace + [(f"bfr:{b['slug']}", odir / "resources.json", bfr_rt)]
        return ((tfk, b["slug"]), (lf, bfr_mask, fm_rt + bfr_rt, trace))
    except Exception as e:
        print(f"  composed  {tfk}+{b['slug']} bfr DNF ({e})")
        return None


def do_dipole(task, args, gt_sources, gt, mask, lf_cache):
    """Invert one cached localfield with one dipole method, score the final chimap, and overwrite the
    single-stage resources.json with the whole-pipeline concatenated trace. Returns the result row
    (or a DNF row on failure)."""
    tfk, b, d = task
    combo = f"{b['slug']}+{d['slug']}" if tfk == "gt" else f"{tfk}+{b['slug']}+{d['slug']}"
    cid = f"{tfk}~{b['slug']}~{d['slug']}-cmp"
    cinfo = {"field_mapping": tfk, "bfr": b["slug"], "dipole": d["slug"]}
    try:
        lf, bfr_mask, upstream_rt, upstream_trace = lf_cache[(tfk, b["slug"])]
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
                  args.work / f"cmp_{cid}.json", meta, args.emit_volumes)
        # The submission page for this composed run must graph the WHOLE pipeline, so overwrite
        # the single-stage resources.json emit_volumes() copied (the dipole's alone) with the
        # concatenation of every stage's trace, in execution order, with cumulative offsets —
        # its span then matches runtime_s and the metrics/NiiVue image on that page.
        _emit_composed_resources(
            cid, upstream_trace + [(f"dipole:{d['slug']}", odir / "resources.json", rt)],
            args.emit_volumes)
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


def do_span(task, args, gt_sources, gt, mask, tf_sources):
    """Run + score one span submission (bfr+dipole / end-to-end), returning its result row (or DNF).

    A bfr+dipole span consumes the total field, so it is composed with a total-field SOURCE — the
    ground truth ("gt") or a field-mapping submission's output — exactly like a BFR method. `task` is
    (span, totalfield-source key); the run is tagged combo={field_mapping: key} and staged
    "bfr+dipole" (gt) or "field-mapping+bfr+dipole" (a field map), so it lands under the matching
    field-mapping on the leaderboard instead of being pinned to the ground-truth field. An end-to-end
    span consumes phase and does its own field-mapping, so it runs once from GT (no upstream field
    map, no combo)."""
    s, tfk = task
    consumes_tf = "totalfield" in s["consumes"]
    upstream_rt, upstream_trace, src = 0.0, [], dict(gt_sources)
    if consumes_tf:
        tfp, tf_mask, upstream_rt, upstream_trace = tf_sources[tfk]
        src["totalfield"], src["mask"] = tfp, tf_mask
        stage = "bfr+dipole" if tfk == "gt" else "field-mapping+bfr+dipole"
        combo = {"field_mapping": tfk}
        # gt reuses the historical "{slug}-cmp" id (so a re-score overwrites the old ground-truth-field
        # span run in place, leaving no orphan); a field-map gets its own "{fm}~{slug}-cmp" id.
        cid = f"{s['slug']}-cmp" if tfk == "gt" else f"{tfk}~{s['slug']}-cmp"
    else:                                       # end-to-end: from GT phase, its own field-mapping
        stage, combo, cid = s["stage"], None, f"{s['slug']}-cmp"
    idir, odir = args.work / f"cmp_{cid}_in", args.work / f"cmp_{cid}_out"
    try:
        prepare_input(s["consumes"], src, idir)
        rt = run_algo(s, idir, odir, args.runner)
        meta = {"id": cid, "slug": s["slug"], "name": s.get("name", s["slug"]), "stage": stage,
                "mode": "composed", "track": args.track, "runtime": upstream_rt + rt}
        if combo is not None:
            meta["combo"] = combo
        r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                  args.work / f"cmp_{cid}.json", meta, args.emit_volumes)
        # A field-mapping-composed span is a two-stage pipeline, so its viewer trace concatenates the
        # field-mapping stage with the span (matching runtime_s); a gt/end-to-end span is a single run.
        if upstream_trace:
            _emit_composed_resources(
                cid, upstream_trace + [(f"{s['stage']}:{s['slug']}", odir / "resources.json", rt)],
                args.emit_volumes)
        m = r["metrics"]
        if r.get("status") == "DNF":
            print(f"  composed  {cid:<34} DNF ({r.get('dnf_reason','')})")
        else:
            print(f"  composed  {cid:<34} chimap xsim={_fmt(m.get('xsim'))} "
                  f"nrmse_dt={_fmt(m.get('nrmse_detrend'), '.2f')}%")
        return r
    except Exception as e:
        print(f"  composed  {cid:<28} DNF ({e})")
        return dnf(cid, s["slug"], s.get("name", s["slug"]), stage, "composed", args.track, combo)


def run_composed(args, algos, gt_sources, gt, mask, shard_i, shard_n, runs: list) -> None:
    """Composed: (field-mapping) x bfr x dipole, chaining real outputs, plus spans.

    Preserves the exact stage ordering, the --focus pinning, the --shard COLUMN partition (a column =
    (totalfield-source, bfr); its bfr localfield is computed in exactly one shard), the bfr-output
    caching reused across dipole methods (the N×M matrix), and the _pmap fan-out per stage. Appends
    result rows to `runs` and flushes the index (unless writing a shard file) after the dipole stage,
    exactly as before."""
    def _owns(index):
        return shard_owns(index, shard_i, shard_n)

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
        else:                                     # a bfr+dipole / end-to-end span
            # A bfr+dipole span consumes the total field, so still compose it with every field-mapping
            # (plus gt); an end-to-end span runs from phase, so it has no field-mapping upstream.
            bfr, dipole, spans = [], [], [f]
            fmap = [a for a in algos if "totalfield" in a["produces"]] if "totalfield" in f["consumes"] else []

    # --shard: own each composed COLUMN = (totalfield-source, bfr) via round-robin over a stable
    # ordering. A column's bfr localfield is computed in exactly one shard (no cross-shard bfr
    # recomputation); a field-map runs only in shards that own a column consuming it.
    fm_keys = ["gt"] + sorted(f["slug"] for f in fmap)
    col_owner = {(tfk, bs): idx for idx, (tfk, bs)
                 in enumerate((tfk, b["slug"]) for tfk in fm_keys for b in sorted(bfr, key=lambda x: x["slug"]))}
    owns_col = lambda tfk, bs: _owns(col_owner.get((tfk, bs), 0))
    # bfr+dipole spans (TGV, NeXtQSM, MEDI, QSMART, …) consume the total field, so each composes with
    # every total-field source (gt + each field-map); treat each (source, span) as its own shard column
    # so it runs in exactly one shard and that shard runs the field-map it needs. end-to-end spans run
    # once from GT phase.
    tf_spans = sorted([s for s in spans if "totalfield" in s["consumes"]], key=lambda x: x["slug"])
    e2e_spans = sorted([s for s in spans if "totalfield" not in s["consumes"]], key=lambda x: x["slug"])
    span_owner = {(tfk, s["slug"]): idx for idx, (tfk, s)
                  in enumerate((tfk, s) for tfk in fm_keys for s in tf_spans)}
    owns_span = lambda tfk, ss: _owns(span_owner.get((tfk, ss), 0))
    if shard_n is not None:
        needed_fm = {tfk for (tfk, bs) in col_owner if tfk != "gt" and owns_col(tfk, bs)}
        needed_fm |= {tfk for (tfk, ss) in span_owner if tfk != "gt" and owns_span(tfk, ss)}
        fmap = [f for f in fmap if f["slug"] in needed_fm]
        e2e_spans = shard_partition(e2e_spans, args.shard)

    # Stage 1 — totalfield sources: the ground-truth field ("gt") plus each field-mapping
    # submission's output (run on raw inputs), so the matrix can start from raw phase.
    # Each source is (totalfield, valid-region mask, cumulative runtime s) so downstream stages
    # inherit any erosion and can accumulate the full pipeline's wall-clock time. The ground-truth
    # field costs nothing to "produce", so its runtime is 0.
    # Each source carries (totalfield, valid-region mask, cumulative runtime s, stage-traces),
    # where stage-traces is the ordered list of (name, resources.json path, duration s) for every
    # stage run so far — so the composed run can concatenate the whole pipeline's memory/CPU trace
    # (not just the final stage's). The ground-truth field ran no stage, so its list is empty.
    tf_sources: dict[str, tuple] = {"gt": (gt / ARTIFACT_FILE["totalfield"], mask, 0.0, [])}

    for res in _pmap(fmap, lambda f: do_fieldmap(f, args, gt_sources, mask)):
        if res:
            tf_sources[res[0]] = (res[1], res[2], res[3], res[4])

    # Stage 2 — bfr: localfield for each (totalfield source, bfr), keyed (tfk, bfr slug).
    # Each entry caches (localfield, valid-region mask, cumulative runtime s) so the dipole
    # inherits any erosion and the upstream field-mapping + BFR wall-clock time.
    lf_cache: dict[tuple, tuple] = {}
    bfr_tasks = [(tfk, tfp, tf_mask, fm_rt, fm_trace, b)
                 for tfk, (tfp, tf_mask, fm_rt, fm_trace) in tf_sources.items()
                 for b in bfr if owns_col(tfk, b["slug"])]  # --shard: only this shard's columns
    for res in _pmap(bfr_tasks, lambda task: do_bfr(task, args, gt_sources)):
        if res:
            lf_cache[res[0]] = res[1]

    # Stage 3 — dipole: invert each cached localfield with every dipole method.
    dip_tasks = [(tfk, b, d) for tfk in tf_sources for b in bfr
                 if (tfk, b["slug"]) in lf_cache for d in dipole]
    for r in _pmap(dip_tasks, lambda task: do_dipole(task, args, gt_sources, gt, mask, lf_cache)):
        runs.append(r)
    if not args.runs_out:
        flush_index(runs)

    # Stage 4 — spans. bfr+dipole spans compose with each total-field source produced above (this
    # shard's owned (source, span) columns only); end-to-end spans run once from GT phase.
    span_tasks = [(s, tfk) for tfk in tf_sources for s in tf_spans if owns_span(tfk, s["slug"])]
    span_tasks += [(s, "gt") for s in e2e_spans]
    for r in _pmap(span_tasks, lambda t: do_span(t, args, gt_sources, gt, mask, tf_sources)):
        runs.append(r)


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
    ap.add_argument("--smoke", action="store_true",
                    help="smoke mode (isolated only): crop inputs to a central box, RUN the method, and "
                         "verify it emits a valid (present/finite/non-empty) output — but do NOT score. "
                         "A fast PR gate that catches broken run.sh / crashes / bad output without the "
                         "full-resolution reconstruction or the (score.yml-duplicated) scoring.")
    ap.add_argument("--smoke-box", type=int, default=96,
                    help="central crop size per spatial axis for --smoke (default 96)")
    ap.add_argument("--fail-on-dnf", action="store_true",
                    help="exit non-zero if any run in scope DNF'd (a submission that couldn't run or "
                         "produce a scorable artifact). Used by evaluate.yml so a broken run.sh / crash "
                         "surfaces as a red check instead of a silently-swallowed DNF.")
    args = ap.parse_args()

    # --shard i/n : this job runs shard i of n. shard_owns(index, ...) is a deterministic round-robin
    # over a stable ordering, so the n shards partition the work with no overlap and no gaps.
    shard_i, shard_n = parse_shard(args.shard)

    inputs, gt = args.dataset / "inputs", args.dataset / "groundtruth"
    mask, params = inputs / "mask.nii.gz", inputs / "params.json"
    # GT-backed source map: inputs for raw artifacts, groundtruth for stage boundaries (shared helper).
    gt_sources = _gt_sources(args.dataset)
    algos = discover_algorithms(args.track)
    if args.include:
        keep = set(args.include.split(","))
        algos = [a for a in algos if a["slug"] in keep]
    if args.exclude:
        drop = set(args.exclude.split(","))
        algos = [a for a in algos if a["slug"] not in drop]
    # The in-vivo (2016 challenge) dataset ships only localfield + chimap ground truth, so ONLY the
    # dipole stage is scorable (ppm localfield -> ppm chimap). Restrict to dipole methods and force
    # isolated mode — there is no field-mapping/BFR GT to feed a composed matrix, so composed would
    # only emit empty/unscorable rows.
    if args.track == "invivo":
        algos = [a for a in algos if a["stage"] == "dipole"]
        if args.mode != "isolated":
            print("[invivo] only the dipole stage is scored — forcing --mode isolated")
            args.mode = "isolated"
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
        run_isolated(args, algos, gt_sources, gt, mask, iso_target, runs)

    # -------- composed: (field-mapping) x bfr x dipole, chaining real outputs --------
    # Dependency order is fieldmap -> bfr -> dipole, so each stage is a barrier; but every
    # combo within a stage is independent, so each stage fans out over the pool.
    if args.mode in ("composed", "both"):
        run_composed(args, algos, gt_sources, gt, mask, shard_i, shard_n, runs)

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
