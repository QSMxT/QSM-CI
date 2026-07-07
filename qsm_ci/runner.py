"""`qsm-ci test` — run one submission on the dev phantom (isolated mode) and score it.

Mirrors scripts/pipeline.py's isolated path for a single algorithm: feed the stage its
ground-truth consumed artifacts, run it, and score the output against ground truth with the exact
scorer the CI uses (qsm_ci.qsm_eval). No results/ are written — this just prints your numbers.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .stages import ARTIFACT_FILE, ARTIFACT_KIND, STAGES

# numpy/scipy/nibabel are imported lazily (inside _score / test_algorithm) so that
# `qsm-ci doctor` and `new` still work in an environment missing the scoring deps.


def _parse_manifest(algo_dir: Path) -> dict:
    spec = algo_dir / "algorithm.yml"
    if not spec.exists():
        raise SystemExit(f"no algorithm.yml in {algo_dir}")
    text = spec.read_text()

    def field(key):
        m = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.M)
        return m.group(1) if m else None

    stage = field("stage")
    if stage not in STAGES:
        raise SystemExit(f"algorithm.yml stage '{stage}' is not a known stage/span")
    return {"dir": algo_dir, "name": field("name") or algo_dir.name,
            "slug": field("slug") or algo_dir.name, "stage": stage,
            "image": field("image")}


def resolve_algo_dir(target: str) -> Path:
    """Accept a slug (algorithms/<slug> or ./<slug>) or a direct path to the folder."""
    p = Path(target)
    for cand in (p, Path("algorithms") / target, Path.cwd() / target):
        if (cand / "algorithm.yml").exists():
            return cand.resolve()
    raise SystemExit(f"could not find an algorithm.yml for '{target}' "
                     f"(looked at {p}, algorithms/{target})")


def _build_env(algo: dict, log) -> str:
    """Resolve the runnable image: build a Dockerfile if present, else pull image:."""
    if (algo["dir"] / "Dockerfile").exists():
        tag = f"qsm-ci-local/{algo['slug']}:latest"
        log(f"⚙ building image from Dockerfile → {tag}")
        subprocess.run(["docker", "build", "-q", "-t", tag, str(algo["dir"])], check=True)
        return tag
    tag = algo["image"]
    if not tag:
        raise SystemExit("algorithm.yml has no image: and no Dockerfile to build")
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode != 0:
        log(f"↓ pulling {tag}")
        subprocess.run(["docker", "pull", tag], check=True)
    return tag


def _prepare_input(consumes, sources, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for art in consumes:
        src = sources.get(art)
        if not src or not Path(src).exists():
            raise SystemExit(f"dev phantom missing '{art}' (expected {src})")
        shutil.copy(src, dest / ARTIFACT_FILE[art])


def _run(algo, input_dir, output_dir, runner, log) -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    t0 = time.time()
    if runner == "docker":
        image = _build_env(algo, log)
        log(f"⚙ running container ({image})")
        subprocess.run([
            "docker", "run", "--rm", "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{algo['dir']}:/algo:ro",
            "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
            image, "bash", "/algo/run.sh",
        ], check=True)
    else:
        log("⚙ running run.sh directly (--runner local)")
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True)
    return time.time() - t0


def _score(recon: Path, artifact: str, gt: Path, mask: Path) -> dict:
    from . import qsm_eval
    kind = ARTIFACT_KIND[artifact]
    r = qsm_eval.load(recon)
    t = qsm_eval.load(gt / ARTIFACT_FILE[artifact])
    m = qsm_eval.load(mask)
    if r.shape != t.shape or r.shape != m.shape:
        raise SystemExit(f"shape mismatch: recon {r.shape}, truth {t.shape}, mask {m.shape}")
    if kind == "field":
        return qsm_eval.field_metrics(r, t, m)
    seg_path = gt / "dseg.nii.gz"
    if seg_path.exists():
        import numpy as np
        seg = np.rint(qsm_eval.load(seg_path)).astype("int32")
        return qsm_eval.challenge_metrics(r, t, m, seg)
    return {"correlation": qsm_eval.correlation(r, t, m), "xsim": qsm_eval.xsim(r, t, m)}


def _print_metrics(name, stage, artifact, runtime, metrics, log):
    log("")
    log(f"  {name}  ·  {stage} → {artifact}  ·  {runtime:.1f}s")
    log("  " + "─" * 34)
    for key, val in metrics.items():
        if isinstance(val, float) and math.isnan(val):
            shown = "—"
        elif isinstance(val, float):
            shown = f"{val:.4f}"
        else:
            shown = str(val)
        log(f"  {key:<20} {shown:>12}")
    log("")


def test_algorithm(target: str, runner: str = "docker", log=print) -> dict:
    from . import data
    algo = _parse_manifest(resolve_algo_dir(target))
    ds = data.ensure_dataset(log=log)
    inputs, gt = ds / "inputs", ds / "groundtruth"
    mask = inputs / "mask.nii.gz"
    sources = {
        "phase": inputs / "phase.nii.gz", "magnitude": inputs / "magnitude.nii.gz",
        "mask": mask, "params": inputs / "params.json",
        "totalfield": gt / "totalfield.nii.gz", "localfield": gt / "localfield.nii.gz",
        "chimap": gt / "chimap.nii.gz",
    }
    stage = algo["stage"]
    log(f"▸ {algo['name']}  [{stage}]  runner={runner}")
    with tempfile.TemporaryDirectory(prefix="qsm-ci-") as td:
        idir, odir = Path(td) / "input", Path(td) / "output"
        _prepare_input(STAGES[stage]["consumes"], sources, idir)
        runtime = _run(algo, idir, odir, runner, log)
        out = {}
        for art in STAGES[stage]["produces"]:
            produced = odir / ARTIFACT_FILE[art]
            if not produced.exists():
                raise SystemExit(f"submission did not write {ARTIFACT_FILE[art]} to /output (DNF)")
            metrics = _score(produced, art, gt, mask)
            _print_metrics(algo["name"], stage, art, runtime, metrics, log)
            out[art] = metrics
    return {"name": algo["name"], "stage": stage, "runtime_s": runtime, "metrics": out}


def check_docker() -> bool:
    try:
        return subprocess.run(["docker", "version"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False
