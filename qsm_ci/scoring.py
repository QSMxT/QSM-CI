"""Shared scoring/sweep primitives — one home for the helpers that scripts/pipeline.py,
scripts/sweep.py and scripts/combo_sweep.py used to each keep their own copy of.

These are the pure-ish building blocks around *running* a submission and *scoring* its artifact:

  - `cli_run_argv(...)`   — build the exact `qsm-ci run …` argv for an isolated container run.
  - `gt_sources(dataset)` — map each canonical artifact to its ground-truth-backed source path.
  - `parse_shard(spec)` / `shard_owns(...)` / `shard_partition(...)` — the `--shard i/n` round-robin
    partition logic (deterministic, order-preserving, no overlap and no gaps across the n shards).
  - `eval_argv(...)`      — build the `python qsm_eval.py …` argv the scorer invokes.

Kept importable without heavy deps at module top: nothing here imports numpy/nibabel/subprocess at
import time (matching the standalone-script style — a bare `python scripts/pipeline.py` must work from
a checkout without the scientific stack installed just to build an argv or parse a shard spec).

The artifact→file map lives in qsm_ci.stages (ARTIFACT_FILE); callers pass it in so this module has no
import cycle with stages and no opinion on where the table lives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def cli_run_argv(algo: dict, input_dir: Path, output_dir: Path, artifact_file: dict,
                 runner: str = "docker", overrides: "dict | None" = None,
                 fmt: "Callable | None" = None) -> list[str]:
    """Build the `qsm-ci run …` argv that reproduces this submission's isolated container run.

    Each consumed artifact becomes a `--<artifact> <input_dir>/<file>` flag (magnitude is optional —
    only passed when present); the produced artifact is written with `-o <output_dir>/<file>`. Any
    `overrides` become `--set NAME=VALUE` (the tuned pass). The CLI owns image resolution, mounting
    run.sh, and injecting the QSMCI_* acquisition env vars — so the scorer no longer duplicates
    (and drifts from) that logic.

    `artifact_file` is the canonical artifact→filename map (qsm_ci.stages.ARTIFACT_FILE). `fmt`, if
    given, formats each override VALUE before it goes into the `--set` string — sweep.py passes its
    grid-value formatter here so a swept float like 8.0 renders as `8` (its long-standing behaviour);
    the default `str(v)` matches pipeline.py / run_algo, so both callers keep their exact output.
    """
    fmt = fmt or str
    produces = algo["produces"]
    argv = ["qsm-ci", "run", str(algo["dir"])]
    for art in algo["consumes"]:
        f = input_dir / artifact_file[art]
        if art == "magnitude" and not f.exists():
            continue  # optional — only some methods use it
        argv += [f"--{art}", str(f)]
    for k, v in (overrides or {}).items():
        argv += ["--set", f"{k}={fmt(v)}"]
    # Single-output stages name the file directly (unchanged); a multi-output stage (χ-separation)
    # gets the output directory and the CLI writes each produced artifact there by canonical name.
    out = output_dir / artifact_file[produces[0]] if len(produces) == 1 else output_dir
    argv += ["-o", str(out), "--runner", runner]
    return argv


def gt_sources(dataset: Path) -> dict[str, Path]:
    """Map each canonical artifact to its ground-truth-backed source path for a dataset dir.

    Each artifact resolves to `<dataset>/inputs/<file>` when that file exists, else
    `<dataset>/groundtruth/<file>` — so an isolated run is fed the exact artifact its stage consumes,
    whichever side of the boundary it lives on. For the QSM sim datasets that means raw acquisition
    (phase/magnitude/mask/params) from inputs/ and the held-out stage boundaries
    (totalfield/localfield/chimap) from groundtruth/. For the χ-separation dataset the local field,
    R2′ and χ_total are *provided* inputs, so they resolve from inputs/ (the phantom's true maps),
    while the scored χ+/χ− source maps stay in groundtruth/.
    """
    inputs, gt = dataset / "inputs", dataset / "groundtruth"
    # Raw acquisition / provided-relaxation artifacts are always public inputs.
    raw = {"phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
           "params": "params.json", "r2prime": "r2prime.nii.gz"}
    # Stage boundaries are held-out ground truth for the QSM pipeline, but *provided* inputs for the
    # χ-separation dataset (the phantom's true local field / χ_total). Prefer inputs/ when present.
    boundary = {"totalfield": "totalfield.nii.gz", "localfield": "localfield.nii.gz",
                "chimap": "chimap.nii.gz"}
    src = {art: inputs / f for art, f in raw.items()}
    src.update({art: (inputs / f if (inputs / f).exists() else gt / f)
                for art, f in boundary.items()})
    return src


def parse_shard(spec: "str | None") -> "tuple[int | None, int | None]":
    """Parse a `--shard i/n` spec into (i, n), or (None, None) when unset. Raises SystemExit with the
    same message pipeline.py used for an out-of-range spec (0 <= i < n)."""
    if not spec:
        return (None, None)
    i, n = (int(x) for x in spec.split("/"))
    if not (0 <= i < n):
        raise SystemExit(f"--shard i/n needs 0 <= i < n, got {spec}")
    return (i, n)


def shard_owns(index: int, shard_i: "int | None", shard_n: "int | None") -> bool:
    """Deterministic round-robin ownership: does shard `shard_i` of `shard_n` own this 0-based index?

    Sharding-off (shard_n is None) owns everything. Otherwise `index % shard_n == shard_i`, so the n
    shards partition a stable ordering with no overlap and no gaps (union of all n == the full set).
    """
    return shard_n is None or index % shard_n == shard_i


def shard_partition(items: "list", spec: "str | None") -> "list":
    """Return the sublist of `items` owned by shard `spec` (`"i/n"`), preserving order.

    A round-robin over `items` by position: shard i keeps items at indices i, i+n, i+2n, … The n
    shards partition `items` exactly (every item in one shard, none in two). `spec` None/"" → all
    items. Handles n > len(items) (some shards get []), 1/1 (all items), etc.
    """
    shard_i, shard_n = parse_shard(spec)
    if shard_n is None:
        return list(items)
    return [x for idx, x in enumerate(items) if shard_owns(idx, shard_i, shard_n)]


def eval_argv(python: str, eval_path: Path, recon: Path, truth: Path, kind: str, mask: Path,
              artifact: str, out_json: Path, *, stage: str, name: str, track: str,
              runtime=None, seg: "Path | None" = None, component: "str | None" = None,
              wm_rois: "Path | None" = None, theta: "Path | None" = None) -> list[str]:
    """Build the `python qsm_eval.py …` argv the scorer subprocess runs.

    This is the flag-assembly the three scoring wrappers (pipeline.score, sweep.score_xsim,
    combo_sweep.score_chi_xsim) all shared, factored out so the exact flags/order can't drift between
    them. Callers still own the mask build (nibabel), the subprocess.run call and what they do with
    the result — those genuinely differ (pipeline records status/meta/volumes; the sweeps only pull
    the metrics dict, run capture_output, and label the run differently), so they stay in-caller.

    `runtime` is only appended when not None; `--seg` only when a seg path is given (the pipeline gates
    this on kind == 'chi' AND the file existing — it passes seg=None otherwise, matching that gate).
    """
    cmd = [python, str(eval_path), "--recon", str(recon), "--truth", str(truth), "--kind", kind,
           "--mask", str(mask), "--artifact", artifact, "--out", str(out_json),
           "--stage", stage, "--name", name, "--track", track]
    if runtime is not None:
        cmd += ["--runtime", str(runtime)]
    if seg is not None:
        cmd += ["--seg", str(seg)]
    if component is not None:  # χ-separation source (para=χ+, dia=χ−) for the source-specific metrics
        cmd += ["--component", component]
    if wm_rois is not None:  # fibre-bundle atlas WM sub-ROIs for the χ− per-ROI MSPE
        cmd += ["--wm-rois", str(wm_rois)]
    if theta is not None:  # fibre-to-B0 angle map for the χ− orientation analysis (MEV)
        cmd += ["--theta", str(theta)]
    return cmd
