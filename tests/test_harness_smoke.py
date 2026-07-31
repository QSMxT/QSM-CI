"""End-to-end smoke test of the pipeline ORCHESTRATION without any real method or container.

scripts/pipeline.py's discover -> isolated/composed -> score -> index path is what the backend PRs
(resource stamping, two-reference in-vivo scoring, id namespacing, index merge) actually change, yet
CI only ran real methods (hours, self-hosted) to touch it. This drives that whole path in seconds on
the container-free `local` runner, pointing discovery at the fixture methods in tests/methods via
QSMCI_ALGORITHMS_DIR — a copy-in-field-out "method" scores correlation ~= 1 against a truth that
equals the input, so the plumbing is verified end to end.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
METHODS = ROOT / "tests" / "methods"


def _save(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(arr.astype("float32"), np.eye(4)), str(path))


def _dataset(root: Path, *, sti: bool = False) -> Path:
    """A tiny dataset where totalfield == localfield == chimap == field, so a copy-through method
    scores ~1. With sti=True also writes a second reference (chimap-sti) for the in-vivo path."""
    field = (np.random.default_rng(0).standard_normal((16, 16, 16)) * 0.05).astype("float32")
    _save(root / "inputs" / "mask.nii.gz", np.ones((16, 16, 16), "float32"))
    (root / "inputs" / "params.json").write_text(
        json.dumps({"TE": [0.004], "B0": 3.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
    for name in ("totalfield", "localfield", "chimap"):
        _save(root / "groundtruth" / f"{name}.nii.gz", field)
    if sti:
        _save(root / "groundtruth" / "chimap-sti.nii.gz", field * 0.9)
    return root


def _run(dataset: Path, runs_out: Path, work: Path, *, mode: str, track: str, include: str) -> list:
    env = {**os.environ, "QSMCI_ALGORITHMS_DIR": str(METHODS)}
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pipeline.py"),
         "--dataset", str(dataset), "--mode", mode, "--runner", "local", "--track", track,
         "--include", include, "--runs-out", str(runs_out), "--work", str(work)],
        cwd=str(ROOT), env=env, check=True)
    return json.loads(runs_out.read_text())


def test_isolated_dipole_scores(tmp_path):
    ds = _dataset(tmp_path / "ds")
    runs = _run(ds, tmp_path / "runs.json", tmp_path / "work",
                mode="isolated", track="sim", include="cp-method")
    cp = [r for r in runs if r["slug"] == "cp-method"]
    assert cp, "cp-method isolated dipole run missing"
    r = cp[0]
    assert r["status"] == "ok" and r["artifact"] == "chimap"
    assert r["metrics"]["correlation"] > 0.99  # truth == input, so a copy is ~perfect
    assert "hfen" in r["metrics"]              # in-vivo/no-seg chi metric set includes HFEN


def test_composed_matrix_runs(tmp_path):
    ds = _dataset(tmp_path / "ds")
    runs = _run(ds, tmp_path / "runs.json", tmp_path / "work",
                mode="composed", track="sim", include="cp-bfr,cp-method")
    composed = [r for r in runs if r.get("mode") == "composed" and r.get("artifact") == "chimap"]
    assert composed, "no composed chimap run produced"
    assert any(r["metrics"].get("correlation", 0) > 0.99 for r in composed)


def test_invivo_two_reference_scoring(tmp_path):
    ds = _dataset(tmp_path / "ds", sti=True)
    runs = _run(ds, tmp_path / "runs.json", tmp_path / "work",
                mode="isolated", track="invivo", include="cp-method")
    cp = [r for r in runs if r["slug"] == "cp-method"]
    assert cp, "cp-method invivo run missing"
    r = cp[0]
    assert r["track"] == "invivo" and r["id"].endswith("-invivo")
    # primary (COSMOS-equivalent) + secondary (STI) metrics both present
    assert r["metrics"]["correlation"] > 0.99
    assert "nrmse" in r["metrics"] and "nrmse_sti" in r["metrics"]
