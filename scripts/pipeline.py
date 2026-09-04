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
                             [--phantom <scripts/datasets.json key>]
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


def write_run_regions(run_id, regions_obj) -> None:
    """Write one run's per-region stats to results/<id>/regions.json — the per-run artifact the web
    submission page fetches, and the findings view pulls per isolated run. It is published to Hugging
    Face alongside the run's volumes and referenced by `regions_url` in index.json, exactly like
    resources.json/resources_url — so the ~3.6 MB of all-runs regional data never bloats the committed
    index or git history. `regions_obj` is the component-keyed block {chi|para|dia: {labels, recon,
    truth}}; an empty/falsy block writes nothing."""
    if not regions_obj:
        return
    d = ROOT / "results" / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "regions.json").write_text(json.dumps(regions_obj, indent=2) + "\n")


# Where a composed pipeline's INTERMEDIATE maps are staged for publishing. Unlike recon/truth/error
# these don't belong to a run — the total field belongs to the field-mapping method and the local
# field to the (field-mapping, background-removal) pair, so every pipeline built on that column shares
# one file. They are keyed by column and namespaced by phantom, and named with the basename they take
# on the Hub, so publishing is a straight directory upload.
INTERMEDIATE_DIR = "_intermediates"


def emit_intermediate(phantom: str, name: str, src: Path) -> None:
    """Stage one per-column intermediate map under results/_intermediates/<phantom>/<name>.nii.gz.

    Best-effort and idempotent: two shards owning different columns of the same field-mapping method
    both write that method's total field, and the copy is small next to the run itself."""
    if not phantom or not Path(src).exists():
        return
    d = ROOT / "results" / INTERMEDIATE_DIR / phantom
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, d / f"{name}.nii.gz")


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


# ---------------------------------------------------------------------------------------------------
# Dataset / phantom registry (scripts/datasets.json) — the single source of truth for every scoring
# dataset. Keyed by phantom id; each entry carries the TRACK whose method family runs on it
# (sim = the QSM pipeline, chisep = χ-separation, invivo = the 2016 dipole challenge), how to locate
# its OSF zip (osf_file literal id and/or osf_env secret name), its local path, a human label, an
# `active` flag (only active phantoms get CI matrix entries), and `default: true` on exactly one
# phantom per track (the default keeps the legacy run-id namespace; the others get a -<phantom>
# suffix so their runs never collide in results/index.json).
# ---------------------------------------------------------------------------------------------------

def load_datasets() -> dict:
    """Load the phantom registry. QSMCI_DATASETS_FILE points it at a fixture registry in tests."""
    p = Path(os.environ.get("QSMCI_DATASETS_FILE") or (ROOT / "scripts" / "datasets.json"))
    return json.loads(p.read_text())


def default_phantom(track: str) -> "str | None":
    """The registry key of `track`'s default phantom (the one that keeps legacy run ids)."""
    for k, v in load_datasets().items():
        if v.get("track") == track and v.get("default"):
            return k
    return None


def phantom_suffix(phantom: "str | None") -> str:
    """Run-id namespace for a phantom: a track's DEFAULT phantom keeps the historical bare ids
    (backward compatible — a re-score overwrites the existing leaderboard entry in place), while a
    non-default phantom of the same track appends `-<phantom-id>` so its runs live in a disjoint id
    space. No phantom given (legacy invocation) means the default phantom: no suffix."""
    if not phantom:
        return ""
    return "" if load_datasets()[phantom].get("default") else f"-{phantom}"


def _yaml_scalar(v) -> str:
    """Render a parsed YAML scalar as the bare token the old regex captured (`\\S+`).

    The previous parser read `stage:`/`image:`/`tuned:`/list items straight out of the text as
    strings, so every consumer downstream expects a `str`. yaml.safe_load instead coerces `520`→int,
    `0.00015`→float, etc. Stringifying restores the old type/shape without a lossy re-parse — and for
    every value in the repo's ymls `str(safe_load(tok)) == tok` (ints, plain floats, and `NeM`
    exponents alike), so the tuned/optional/stage strings are byte-identical to the regex output."""
    return str(v)


def _tuned_overrides(doc: dict, dataset: str = "sim", phantom: "str | None" = None) -> dict:
    """Extract `{param: tuned_value}` for a dataset (`sim` / `invivo` / `chisep`) from a parsed
    algorithm.yml `parameters:` block — the settings optimised on that dataset (each parameter may
    carry a `tuned:` alongside its `default:`). `tuned` is either a per-dataset MAP
    (`tuned: {sim: .., invivo: .., chisep: ..}`) or a legacy SCALAR (which applies to the in-silico/sim
    dataset only). So sim keeps reading the existing scalar tunings, and a method only gets an
    in-vivo / chi-sep tuned variant once it declares `tuned.invivo` / `tuned.chisep`.

    With multiple phantoms per track, the map may ALSO be keyed by a specific phantom id
    (`tuned: {chisep: .., ridani-3t-aniso: ..}`). Lookup order per parameter: the exact `phantom` id
    key -> the track-family `dataset` key -> the legacy scalar (sim only). So a method tuned on the
    default chisep phantom keeps applying that tuning to every chisep-track phantom until it declares
    a phantom-specific value.

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
        if isinstance(t, dict):
            val = t.get(phantom) if phantom is not None else None
            if val is None:
                val = t.get(dataset)
        else:
            val = t if dataset == "sim" else None
        if val is None:
            continue
        out[_yaml_scalar(item["name"])] = _yaml_scalar(val)
    return out


def discover_algorithms(track: str = "sim", phantom: "str | None" = None) -> list[dict]:
    # `track` selects which dataset's tuned params each method carries: a chi-separation method is only
    # ever scored on a chisep-track phantom (→ "chisep"), otherwise the in-vivo run uses "invivo" and
    # everything else "sim". So the tuned variant a run expands is the one optimised on ITS dataset.
    # `phantom` (a scripts/datasets.json key) further narrows that: a `tuned:` map keyed with the exact
    # phantom id wins over the track-family key (see _tuned_overrides).
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
        # A submission may declare `ci_skip: true` to stay in the repo (reviewable code/weights) but
        # NOT be scored — e.g. it needs a runner tier QSM-CI doesn't have yet (DIP-UP is GPU-only; CPU
        # is impractical). Discovery is the single choke point for every mode (shard sweep, --focus,
        # composed, local), so skipping here makes the method invisible to the whole scorer. Un-skip
        # once the required runner exists.
        if doc.get("ci_skip"):
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
            "tuned": _tuned_overrides(doc, "chisep" if s in ("chi-separation", "r2prime-generation")
                                      else ("invivo" if track == "invivo" else "sim"), phantom),
            # Optional per-method smoke-crop size (voxels): a slow per-voxel method (e.g. DECOMPOSE)
            # can shrink the --smoke gate's central box so the PR check stays fast; None = CLI default.
            "smoke_box": doc.get("smoke_box"),
            # Optional per-method parameter overrides applied ONLY on the --smoke gate (merged over the
            # variant's params before the run). Lets an expensive iterative/DL method cut its work for
            # the "does it run?" PR check while score.yml (no --smoke) still uses the full defaults —
            # e.g. MoDIP caps its per-subject optimization to a few epochs here, 500 when scored.
            "smoke_params": doc.get("smoke_params") or {},
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
          emit_volumes_on: bool = False, truth: "Path | None" = None) -> dict:
    kind = ARTIFACT_KIND[artifact]
    # The reference defaults to gt_dir/<canonical file>; `truth` overrides it for artifacts whose
    # reference is NOT a groundtruth/ file — a generated r2prime scores against the phantom's true
    # R2′, which is an INPUT of the χ-separation datasets (inputs/r2prime.nii.gz).
    truth = truth if truth is not None else gt_dir / ARTIFACT_FILE[artifact]
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
    # χ− per-ROI MSPE + orientation analysis (MEV) need the fibre-bundle WM sub-ROI atlas and the
    # fibre-to-B0 angle map, shipped in groundtruth as wm_rois.nii.gz / theta.nii.gz (the Ridani
    # reproduction datasets carry them; others don't → those χ− metrics are simply omitted).
    dia = kind == "chisep" and component == "dia"
    wm_rois = gt_dir / "wm_rois.nii.gz"
    theta = gt_dir / "theta.nii.gz"
    cmd = eval_argv(sys.executable, EVAL, recon, truth, kind, mask,
                    artifact, out_json, stage=meta["stage"], name=meta["name"], track=meta["track"],
                    runtime=meta.get("runtime"),
                    seg=seg if use_seg else None,
                    component=component,
                    wm_rois=wm_rois if (dia and wm_rois.exists()) else None,
                    theta=theta if (dia and theta.exists()) else None)
    subprocess.run(cmd, check=True)
    result = json.loads(out_json.read_text())
    # Per-region descriptive stats (present when the scorer got a seg): key the block by source —
    # 'chi' for a QSM map, 'para'/'dia' for a χ-sep component — so every run's `regions` payload has
    # one shape. It is written to a PER-RUN file results/<id>/regions.json (published to HF with the
    # run's volumes, then referenced by regions_url in index.json — exactly like resources.json), not
    # into index.json. For a plain QSM run we write it here and drop it from the row; a χ-sep
    # component keeps it on the returned row so _score_chisep can fold χ+ and χ− into ONE per-run file.
    if "regions" in result:
        result["regions"] = {component or "chi": result["regions"]}
        if component is None and "id" in meta:
            write_run_regions(meta["id"], result.pop("regions"))
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
        emit_volumes(meta["id"], recon, truth, raw_mask,
                     resources=res if res.exists() else None)
    return result


def id_suffix(track: str) -> str:
    """Run-id namespace for a track. The QSM sim track keeps the historical bare ids (`<slug>-iso`,
    `<slug>-cmp`, …) so a re-score overwrites the existing leaderboard entry in place; every other
    track (currently just `invivo`) appends `-<track>` so its runs live in a disjoint id space and
    never collide with the sim entries in results/index.json."""
    return "" if track == "sim" else f"-{track}"


# Tracks with NO ground truth (e.g. `repro` — the multi-scanner harmonization acquisitions): the
# composed matrix runs from raw inputs only (no gt total-field source), and each run's χ map is
# validated + archived by collect() instead of scored — the evaluation happens ACROSS runs
# (test-retest / inter-scanner agreement), after all acquisitions are reconstructed.
NO_GT_TRACKS = {"repro"}


def collect(recon: Path, mask: Path, meta: dict) -> dict:
    """No-ground-truth 'scoring': validate one run's χ map and archive it for cross-run analysis.

    Reproducibility-track runs are compared with EACH OTHER (same subject, different scanner/
    protocol/run), so there is nothing to score per run. Check the output is usable, record cheap
    within-mask stats, and keep the chimap under results/<id>/recon.nii.gz where the reproducibility
    evaluator and the web viewer find it."""
    import nibabel as nib
    import numpy as np
    row = {"name": meta["name"], "track": meta["track"], "stage": meta["stage"],
           "mode": meta["mode"], "runtime_s": round(meta.get("runtime") or 0.0, 1)}
    row.update({k: meta[k] for k in ("id", "slug", "variant", "params", "combo") if k in meta})
    try:
        data = nib.load(str(recon)).get_fdata()
        m = nib.load(str(mask)).get_fdata() > 0.5
        vals = data[m][np.isfinite(data[m])]
        if vals.size == 0 or not np.any(vals):
            row.update({"status": "DNF", "dnf_reason": "non-finite output (unusable)"})
            return row
        row["status"] = "ok"
        row["metrics"] = {"chi_mean": round(float(vals.mean()), 6),
                          "chi_sd": round(float(vals.std()), 6)}
        d = ROOT / "results" / meta["id"]
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(recon, d / "recon.nii.gz")
        res = recon.parent / "resources.json"
        if res.exists():
            shutil.copy(res, d / "resources.json")
    except Exception as e:  # noqa: BLE001 — one bad run must not sink the batch
        row.update({"status": "DNF", "dnf_reason": str(e)})
    return row


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


def _stamp_phantom(rows: list, phantom: "str | None") -> list:
    """Record which phantom (scripts/datasets.json key) each run row was scored on. Only stamped when
    --phantom was given; older index entries (and legacy invocations) carry no field, and consumers
    treat absence as the track's default phantom."""
    if phantom:
        for r in rows:
            r["phantom"] = phantom
    return rows


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
    so a long run's progress is visible on the leaderboard as it goes. Per-region stats never travel
    on the rows — they are written to per-run results/<id>/regions.json files at score time (see
    write_run_regions) and surfaced via regions_url, so index.json stays lean."""
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


def _score_chisep(a, sfx, variant, overrides, odir, gt, mask, rt, args,
                  rid=None, mode="isolated", stage=None, combo=None):
    """Score a χ-separation run's two source maps (χ+, χ−) and fold them into ONE leaderboard row with
    para_*/dia_* prefixed metrics and domain='chisep' — the chi-sep leaderboard shows one row per
    method with χ+ vs χ− columns, not two separate rows. A DNF in either component marks the row DNF.

    The defaults score an isolated run under the historical `<slug>-iso<sfx>` id; the GRE-only composed
    matrix (run_chisep_composed) passes its own `rid`, mode="composed", the combined stage string and a
    `combo` dict ({r2prime_generation, chi_separation}), reusing the same two-component fold.

    Metrics per source: xsim/nrmse/correlation, region leakage (dia_iron_leak = mean |χ−| in the
    iron/DGM+vein regions where χ− should be ~0; para_calc_leak = mean |χ+| in calcification), and the
    whole-brain regression leakage (para_leak / dia_leak) from _chisep_leakage."""
    rid = rid or f"{a['slug']}-iso{sfx}"
    stage = stage or a["stage"]
    regobj = {}  # accumulate χ+ / χ− region blocks → ONE per-run results/<id>/regions.json below
    row = {"id": rid, "slug": a["slug"], "name": a.get("name", a["slug"]), "stage": stage, "mode": mode,
           "track": args.track, "runtime_s": rt, "variant": variant, "domain": "chisep",
           "kind": "chisep", "metrics": {}, "status": "ok"}
    if overrides:
        row["params"] = overrides
    if combo:
        row["combo"] = combo
    for art in a["produces"]:
        pfx = CHISEP_PREFIX.get(art, art)
        meta = {"id": f"{rid}-{pfx}", "slug": a["slug"], "name": a["slug"], "stage": stage,
                "mode": mode, "track": args.track, "runtime": rt, "variant": variant}
        # emit_volumes off: the two components would collide on one id; chi-sep viewer volumes are a
        # later feature. We only need each component's metrics here.
        r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                  args.work / f"{mode[:3]}_{rid}_{pfx}.json", meta, emit_volumes_on=False)
        for k, v in (r.get("metrics") or {}).items():
            row["metrics"][f"{pfx}_{k}"] = v
        if r.get("regions"):  # per-component regional stats ({'para': …} / {'dia': …})
            regobj.update(r["regions"])
        if r.get("status") == "DNF":
            row["status"], row["dnf_reason"] = "DNF", r.get("dnf_reason", "")
        m = r.get("metrics") or {}
        shown = ("DNF" if r.get("status") == "DNF"
                 else f"xsim={_fmt(m.get('xsim'))} nrmse={_fmt(m.get('nrmse'), '.2f')}%")
        print(f"  {mode:<9} {rid:<16} {variant:<8} {art:<11} {shown}")
    if row["status"] != "DNF":  # whole-brain χ+↔χ− leakage (needs both GT + both recon maps)
        lk = _chisep_leakage(odir, gt, mask)
        if lk:
            row["metrics"].update(lk)
            print(f"  {mode:<9} {rid:<16} {variant:<8} {'leakage':<11} "
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
    write_run_regions(rid, regobj)  # one per-run file carrying both χ+ and χ− region blocks
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
    # + track namespace + phantom namespace (run ids): the track's default phantom adds nothing
    # (legacy ids preserved); a non-default phantom appends -<phantom-id>.
    idsfx = sfx + id_suffix(args.track) + getattr(args, "phantom_sfx", "")
    idir = args.work / f"iso_{a['slug']}{idsfx}_in"
    odir = args.work / f"iso_{a['slug']}{idsfx}_out"
    try:
        prepare_input(a["consumes"], gt_sources, idir)
        run_overrides = overrides
        if args.smoke:
            _smoke_crop(idir, a["consumes"], a.get("smoke_box") or args.smoke_box)
            # Fold in any --smoke-only param overrides (e.g. MoDIP's few-epoch cap) on top of the
            # variant's params. score.yml runs without --smoke, so it keeps the full defaults.
            if a.get("smoke_params"):
                run_overrides = {**(overrides or {}), **a["smoke_params"]}
        rt = run_algo(a, idir, odir, args.runner, run_overrides)
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
            # A generated r2prime scores against the phantom's TRUE R2′ — an input of the χ-separation
            # datasets (gt_sources maps it to inputs/r2prime.nii.gz), not a groundtruth/ file.
            r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                      args.work / f"iso_{a['slug']}{idsfx}.json", meta, args.emit_volumes,
                      truth=gt_sources.get(art) if art == "r2prime" else None)
            if a["stage"] == "r2prime-generation":
                # Group R2′ generators with the χ-separation family in results/index.json — they only
                # run on chisep-track phantoms and surface on that leaderboard (stage distinguishes them).
                r["domain"] = "chisep"
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
        runs.extend(_stamp_phantom(out, getattr(args, "phantom", None)))
    if not args.runs_out:
        flush_index(runs)


# ---------------------------------------------------------------------------------------------------
# Composed evaluation: (field-mapping) x bfr x dipole, chaining real outputs, plus spans. Dependency
# order is fieldmap -> bfr -> dipole, so each stage is a barrier; every combo within a stage is
# independent, so each stage fans out over the pool. bfr outputs are cached and reused across dipole
# methods (the N×M matrix). Hoisted from main()'s nested closures — everything they captured (args,
# the GT source map, the GT dir, the raw mask, the caches) is now passed explicitly.
# ---------------------------------------------------------------------------------------------------

def tf_emit_owner(col_owner, span_owner, owns_col, owns_span) -> set:
    """--emit-intermediates: which total-field sources THIS shard is responsible for publishing.

    The viewer's intermediate maps are per COLUMN, not per pipeline, so each must be written once per
    acquisition however the matrix is split up. A bfr's localfield already is: its column belongs to
    exactly one shard. A field map is not — it is RE-RUN in every shard that owns a column consuming
    it. So pin publication to the shard owning the FIRST column that consumes it (bfr columns in
    their stable order, then span columns): across the n shards each field map is written exactly
    once, for any n. Sharding off owns every column, so every source comes back.

    A --focus run isn't sharded, so it publishes every field map it built. When the focus is a bfr
    those are unchanged, and re-publishing them is near-free (identical content is deduplicated
    Hub-side) — and it keeps the set self-healing if one ever went missing. What the caller should
    avoid is emitting from a run that rebuilds the upstream purely to feed something else: repro.yml
    only passes --emit-intermediates when the changed slug is itself a field-mapping or bfr method."""
    first = {}
    for tfk, bs in col_owner:
        first.setdefault(tfk, ("col", tfk, bs))
    for tfk, ss in span_owner:
        first.setdefault(tfk, ("span", tfk, ss))
    return {tfk for tfk, (kind, t, x) in first.items()
            if (owns_col(t, x) if kind == "col" else owns_span(t, x))}


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
    cid = f"{tfk}~{b['slug']}~{d['slug']}-cmp" + getattr(args, "phantom_sfx", "")
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
        if args.track in NO_GT_TRACKS:
            r = collect(odir / "chimap.nii.gz", mask, meta)
        else:
            r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                      args.work / f"cmp_{cid}.json", meta, args.emit_volumes)
        # The submission page for this composed run must graph the WHOLE pipeline, so overwrite
        # the single-stage resources.json emit_volumes() copied (the dipole's alone) with the
        # concatenation of every stage's trace, in execution order, with cumulative offsets —
        # its span then matches runtime_s and the metrics/NiiVue image on that page.
        _emit_composed_resources(
            cid, upstream_trace + [(f"dipole:{d['slug']}", odir / "resources.json", rt)],
            args.emit_volumes)
        m = r.get("metrics") or {}
        if r.get("status") == "DNF":
            print(f"  composed  {combo:<34} DNF ({r.get('dnf_reason','')})")
        elif args.track in NO_GT_TRACKS:
            print(f"  composed  {combo:<34} chimap collected "
                  f"(mean={_fmt(m.get('chi_mean'))} sd={_fmt(m.get('chi_sd'))})")
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
    cid += getattr(args, "phantom_sfx", "")     # non-default phantom -> disjoint id space
    idir, odir = args.work / f"cmp_{cid}_in", args.work / f"cmp_{cid}_out"
    try:
        prepare_input(s["consumes"], src, idir)
        rt = run_algo(s, idir, odir, args.runner)
        meta = {"id": cid, "slug": s["slug"], "name": s.get("name", s["slug"]), "stage": stage,
                "mode": "composed", "track": args.track, "runtime": upstream_rt + rt}
        if combo is not None:
            meta["combo"] = combo
        if args.track in NO_GT_TRACKS:
            r = collect(odir / "chimap.nii.gz", mask, meta)
        else:
            r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                      args.work / f"cmp_{cid}.json", meta, args.emit_volumes)
        # A field-mapping-composed span is a two-stage pipeline, so its viewer trace concatenates the
        # field-mapping stage with the span (matching runtime_s); a gt/end-to-end span is a single run.
        if upstream_trace:
            _emit_composed_resources(
                cid, upstream_trace + [(f"{s['stage']}:{s['slug']}", odir / "resources.json", rt)],
                args.emit_volumes)
        m = r.get("metrics") or {}
        if r.get("status") == "DNF":
            print(f"  composed  {cid:<34} DNF ({r.get('dnf_reason','')})")
        elif args.track in NO_GT_TRACKS:
            print(f"  composed  {cid:<34} chimap collected "
                  f"(mean={_fmt(m.get('chi_mean'))} sd={_fmt(m.get('chi_sd'))})")
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
        elif f["stage"] in ("chi-separation", "r2prime-generation"):
            # χ-separation / R2′-generation never enter the QSM matrix; their GRE-only combos are
            # run_chisep_composed's job (called instead of this on chisep-track phantoms).
            fmap, bfr, dipole, spans = [], [], [], []
        else:                                     # a bfr+dipole / end-to-end span
            # A bfr+dipole span consumes the total field, so still compose it with every field-mapping
            # (plus gt); an end-to-end span runs from phase, so it has no field-mapping upstream.
            bfr, dipole, spans = [], [], [f]
            fmap = [a for a in algos if "totalfield" in a["produces"]] if "totalfield" in f["consumes"] else []

    # A no-ground-truth track has no gt total field to chain from: every pipeline starts from a
    # real field-mapping submission (or is an end-to-end span running from raw phase).
    no_gt = args.track in NO_GT_TRACKS

    # --shard: own each composed COLUMN = (totalfield-source, bfr) via round-robin over a stable
    # ordering. A column's bfr localfield is computed in exactly one shard (no cross-shard bfr
    # recomputation); a field-map runs only in shards that own a column consuming it.
    fm_keys = ([] if no_gt else ["gt"]) + sorted(f["slug"] for f in fmap)
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
    # --emit-intermediates: which field maps THIS shard publishes (see tf_emit_owner).
    emit_inter = getattr(args, "emit_intermediates", False)
    emit_tf = tf_emit_owner(col_owner, span_owner, owns_col, owns_span) if emit_inter else set()

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
    tf_sources: dict[str, tuple] = {} if no_gt else {
        "gt": (gt / ARTIFACT_FILE["totalfield"], mask, 0.0, [])}

    for res in _pmap(fmap, lambda f: do_fieldmap(f, args, gt_sources, mask)):
        if res:
            tf_sources[res[0]] = (res[1], res[2], res[3], res[4])
            if res[0] in emit_tf:
                emit_intermediate(args.phantom, f"{res[0]}__totalfield", res[1])

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
            if emit_inter:   # this shard owns the column, so this is the only place it is written
                emit_intermediate(args.phantom, f"{res[0][0]}_{res[0][1]}__localfield", res[1][0])

    # --columns-only stops here: the two upstream stages ARE the whole job when all we want is the
    # per-column total field / local field for the viewer. That is 2 + 2x12 = 26 runs per harmonization
    # acquisition instead of the 660-pipeline matrix, because the dipole stage is what multiplies out.
    if getattr(args, "columns_only", False):
        print(f"  columns-only: {len(tf_sources)} field map(s), {len(lf_cache)} local field(s) — "
              "skipping the dipole stage and spans")
        return

    # Stage 3 — dipole: invert each cached localfield with every dipole method.
    dip_tasks = [(tfk, b, d) for tfk in tf_sources for b in bfr
                 if (tfk, b["slug"]) in lf_cache for d in dipole]
    for r in _pmap(dip_tasks, lambda task: do_dipole(task, args, gt_sources, gt, mask, lf_cache)):
        runs.extend(_stamp_phantom([r], getattr(args, "phantom", None)))
    if not args.runs_out:
        flush_index(runs)

    # Stage 4 — spans. bfr+dipole spans compose with each total-field source produced above (this
    # shard's owned (source, span) columns only); end-to-end spans run once from GT phase.
    span_tasks = [(s, tfk) for tfk in tf_sources for s in tf_spans if owns_span(tfk, s["slug"])]
    span_tasks += [(s, "gt") for s in e2e_spans]
    for r in _pmap(span_tasks, lambda t: do_span(t, args, gt_sources, gt, mask, tf_sources)):
        runs.extend(_stamp_phantom([r], getattr(args, "phantom", None)))


# ---------------------------------------------------------------------------------------------------
# GRE-only composed evaluation (chisep-track phantoms): r2prime-generation × chi-separation.
#
# The GRE-only condition asks: what does χ-separation sacrifice when no spin-echo acquisition provides
# a measured R2 (so no true R2′ = R2* − R2)? Each R2′ GENERATOR estimates R2′ from the multi-echo GRE
# magnitude alone; its output then replaces the phantom's true r2prime for every R2′-consuming
# χ-separation method, with all other inputs unchanged (still the isolated ground-truth boundary).
# That isolates exactly ONE variable — R2′ fidelity — so a composed run pairs 1:1 with the method's
# isolated run (same GT everywhere else) and the leaderboard can chart "full acquisition vs GRE-only"
# per method. χ-sep methods that never read r2prime (e.g. R2*-QSM, DECOMPOSE) are natively GRE-only;
# their isolated runs already ARE the GRE-only condition, so they get no combos here.
# ---------------------------------------------------------------------------------------------------

def do_r2gen(g, args, gt_sources):
    """Run one R2′ generator on the raw GRE inputs, returning (slug, r2prime path, runtime, trace)
    or None on DNF (its combos are skipped, mirroring a DNF'd field-mapping)."""
    idir, odir = args.work / f"cmp_r2g_{g['slug']}_in", args.work / f"cmp_r2g_{g['slug']}_out"
    try:
        prepare_input(g["consumes"], gt_sources, idir)
        rt = run_algo(g, idir, odir, args.runner)
        r2p = odir / ARTIFACT_FILE["r2prime"]
        if not r2p.exists():
            raise FileNotFoundError("r2prime.nii.gz not written")
        return (g["slug"], r2p, rt, [(f"r2prime-generation:{g['slug']}", odir / "resources.json", rt)])
    except Exception as e:
        print(f"  composed  r2gen {g['slug']} DNF ({e}) — skipping its pipelines")
        return None


def do_chisep_composed(task, args, gt_sources, gt, mask, r2p_cache):
    """Run one (R2′ generator, χ-separation method) combo: the generator's cached R2′ replaces the
    true r2prime, everything else stays at the ground-truth boundary. Scored exactly like an isolated
    χ-sep run (two components folded into one row) under `<gen>~<sep>-cmp` with mode=composed and
    combo={r2prime_generation, chi_separation}. The full brain mask is kept — an R2′ of 0 is a valid
    value, so (unlike an eroding BFR) a generator's zero voxels must not shrink the analysis region."""
    gk, c = task
    cid = f"{gk}~{c['slug']}-cmp" + getattr(args, "phantom_sfx", "")
    combo = {"r2prime_generation": gk, "chi_separation": c["slug"]}
    stage = "r2prime-generation+chi-separation"
    try:
        r2p, gen_rt, gen_trace = r2p_cache[gk]
        src = dict(gt_sources); src["r2prime"] = r2p
        idir, odir = args.work / f"cmp_{cid}_in", args.work / f"cmp_{cid}_out"
        prepare_input(c["consumes"], src, idir)
        rt = run_algo(c, idir, odir, args.runner)
        row = _score_chisep(c, "", "default", None, odir, gt, mask, gen_rt + rt, args,
                            rid=cid, mode="composed", stage=stage, combo=combo)
        _emit_composed_resources(
            cid, gen_trace + [(f"chi-separation:{c['slug']}", odir / "resources.json", rt)],
            args.emit_volumes)
        return row
    except Exception as e:
        print(f"  composed  {cid:<34} DNF ({e})")
        row = dnf(cid, c["slug"], c.get("name", c["slug"]), stage, "composed", args.track, combo)
        row["domain"] = "chisep"
        return row


def run_chisep_composed(args, algos, gt_sources, gt, mask, runs: list) -> None:
    """The GRE-only matrix: every R2′ generator × every R2′-consuming χ-separation method.

    Focus semantics (mirrors score.yml's job ownership so a full re-run never runs a combo twice):
    a χ-separation method's --focus job owns ALL its combos (every generator × it); a generator's
    --focus job runs NO combos here (score.yml fans a changed generator out into the χ-sep methods'
    focus jobs instead). Unfocused runs (local full scoring) enumerate the whole grid, --shard
    round-robin over (generator, method) pairs; a generator is (re)run in each shard that owns one
    of its pairs — generators are cheap relative to the χ-sep methods they feed."""
    gens = sorted((a for a in algos if a["stage"] == "r2prime-generation"), key=lambda a: a["slug"])
    seps = sorted((a for a in algos if a["stage"] == "chi-separation" and "r2prime" in a["consumes"]),
                  key=lambda a: a["slug"])
    if args.focus:
        f = next((a for a in algos if a["slug"] == args.focus), None)
        if f is None or f["stage"] != "chi-separation" or "r2prime" not in f["consumes"]:
            return  # a generator focus (isolated-only here) or a non-χ-sep / GRE-native focus
        seps = [f]
    if not gens or not seps:
        return
    pairs = shard_partition([(g, c) for g in gens for c in seps], args.shard)
    if not pairs:
        return

    # Stage 1 — each generator needed by this shard's pairs runs once on the raw GRE inputs,
    # SERIALLY (like stage 2): with three generators, the pool (QSM_CI_JOBS=2) ran the two ONNX
    # U-Nets (r2primenet + r2primenet-7t) concurrently, and on the 6-echo Ridani phantoms that
    # OOM-killed every hosted focus job's VM ("runner received a shutdown signal", 24 jobs,
    # 2026-08-26). Generators are seconds-to-minutes each; cross-method parallelism comes from the
    # CI job matrix.
    need = {g["slug"]: g for g, _ in pairs}
    r2p_cache: dict[str, tuple] = {}
    for g in need.values():
        res = do_r2gen(g, args, gt_sources)
        if res:
            r2p_cache[res[0]] = (res[1], res[2], res[3])

    # Stage 2 — every (generator, χ-sep method) pair with a live generator, run SERIALLY. A focus
    # job's pairs are N generators × the SAME method, so fanning them over the pool runs N copies
    # of that method concurrently — which doubles a memory-heavy DL method's peak and OOM-killed
    # susep-net's combos on the 16 GB hosted runner (two whole-volume torch containers at once,
    # exit 137). Parallelism across methods comes from the CI job matrix, not from within one job.
    tasks = [(g["slug"], c) for g, c in pairs if g["slug"] in r2p_cache]
    for t in tasks:
        r = do_chisep_composed(t, args, gt_sources, gt, mask, r2p_cache)
        runs.extend(_stamp_phantom([r], getattr(args, "phantom", None)))
    if not args.runs_out:
        flush_index(runs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=None,
                    help="dataset dir with inputs/ + groundtruth/. Default: the --phantom's registry "
                         "path when --phantom is given, else data/sim/dev")
    ap.add_argument("--phantom", default=None,
                    help="which phantom (scripts/datasets.json key) this run scores on. The track's "
                         "default phantom keeps legacy run ids; a non-default phantom namespaces its "
                         "run ids with -<phantom-id> and its rows carry a `phantom` field. Omitted = "
                         "the track's default phantom (legacy behaviour, no field stamped).")
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
    ap.add_argument("--emit-intermediates", action="store_true",
                    help="stage each composed COLUMN's intermediate map (the field-mapping stage's "
                         "totalfield, the background-removal stage's localfield) under "
                         "results/_intermediates/<phantom>/ for publishing to the viewer. Requires "
                         "--phantom (the files are namespaced by acquisition).")
    ap.add_argument("--columns-only", action="store_true",
                    help="run only the field-mapping and background-removal stages, then stop — no "
                         "dipole inversion, no spans, no result rows. Paired with "
                         "--emit-intermediates this regenerates just the viewer's intermediate maps.")
    ap.add_argument("--fail-on-dnf", action="store_true",
                    help="exit non-zero if any run in scope DNF'd (a submission that couldn't run or "
                         "produce a scorable artifact). Used by evaluate.yml so a broken run.sh / crash "
                         "surfaces as a red check instead of a silently-swallowed DNF.")
    args = ap.parse_args()

    # --shard i/n : this job runs shard i of n. shard_owns(index, ...) is a deterministic round-robin
    # over a stable ordering, so the n shards partition the work with no overlap and no gaps.
    shard_i, shard_n = parse_shard(args.shard)

    # --phantom: validate against the registry and derive its run-id namespace ("" for the track's
    # default phantom, "-<phantom-id>" otherwise) + the dataset path when --dataset wasn't given.
    if args.phantom:
        reg = load_datasets()
        if args.phantom not in reg:
            raise SystemExit(f"unknown phantom '{args.phantom}' — add it to scripts/datasets.json")
        args.phantom_sfx = phantom_suffix(args.phantom)
        args.phantom_track = reg[args.phantom].get("track")
        if args.dataset is None:
            args.dataset = ROOT / reg[args.phantom]["path"]
    else:
        args.phantom_sfx = ""
        args.phantom_track = None
    if args.dataset is None:
        args.dataset = ROOT / "data/sim/dev"
    if args.emit_intermediates and not args.phantom:
        raise SystemExit("--emit-intermediates needs --phantom: the intermediates are shared across "
                         "pipelines and namespaced by acquisition")
    if args.columns_only and args.mode != "composed":
        # The columns exist only in the composed matrix; an isolated run would be computed and then
        # thrown away, since --columns-only writes no result rows.
        print("[columns-only] the field-mapping/background-removal columns are composed — forcing "
              "--mode composed")
        args.mode = "composed"

    inputs, gt = args.dataset / "inputs", args.dataset / "groundtruth"
    mask, params = inputs / "mask.nii.gz", inputs / "params.json"
    # GT-backed source map: inputs for raw artifacts, groundtruth for stage boundaries (shared helper).
    gt_sources = _gt_sources(args.dataset)
    algos = discover_algorithms(args.track, args.phantom)
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
    # A no-ground-truth track (see NO_GT_TRACKS) has no stage boundaries to feed isolated runs, so
    # only the composed matrix — real field-mapping -> bfr -> dipole chains plus spans, all from raw
    # inputs — is meaningful. Runs are collected (validated + archived), not scored.
    if args.track in NO_GT_TRACKS and args.mode != "composed":
        print(f"[{args.track}] no ground truth — forcing --mode composed (runs collected, not scored)")
        args.mode = "composed"
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

    # -------- composed --------
    # A chisep-track phantom's composed matrix is the GRE-only grid (r2prime-generation ×
    # chi-separation); everything else runs the QSM matrix ((field-mapping) x bfr x dipole, chaining
    # real outputs — dependency order fieldmap -> bfr -> dipole, each stage a barrier, every combo
    # within a stage independent so each stage fans out over the pool).
    if args.mode in ("composed", "both"):
        if args.phantom_track == "chisep":
            run_chisep_composed(args, algos, gt_sources, gt, mask, runs)
        else:
            run_composed(args, algos, gt_sources, gt, mask, shard_i, shard_n, runs)

    # --columns-only produces intermediate MAPS, not scored runs; there is nothing to merge, and
    # writing an empty runs list would churn index.json (or hand the caller an empty shard file).
    if args.columns_only:
        print("\ncolumns-only: no result rows to write "
              f"(intermediates under results/{INTERMEDIATE_DIR}/{args.phantom or '<phantom>'}/)")
        return

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
