"""End-to-end smoke test of the pipeline ORCHESTRATION without any real method or container.

scripts/pipeline.py's discover -> isolated/composed -> score -> index path is what the backend PRs
(resource stamping, two-reference in-vivo scoring, id namespacing, index merge) actually change, yet
CI only ran real methods (hours, self-hosted) to touch it. This drives that whole path in seconds on
the container-free `local` runner, pointing discovery at the fixture methods in tests/methods via
QSMCI_ALGORITHMS_DIR.

The fixture dataset's three ground-truth volumes (totalfield, localfield, chimap) are DISTINCT
deterministic arrays with known pairwise correlations, and the mask covers only a central cube
outside of which the χ map is sign-flipped. A copy-through "method" therefore scores exactly the
correlation between the artifact it actually copied and the truth it was scored against, within the
mask — so a run fed the wrong artifact (the total field where the local field belongs), or scored
over the whole volume instead of the mask, lands on a different number and fails. When every volume
was the same array, any of those mistakes still scored 1.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import qsm_eval

ROOT = Path(__file__).resolve().parent.parent
METHODS = ROOT / "tests" / "methods"
SHAPE = (16, 16, 16)
TOL = 1e-6  # the scorer runs the same correlation() on the same float32 voxels


def _save(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(arr.astype("float32"), np.eye(4)), str(path))


def _volumes() -> dict:
    """Deterministic, pairwise-distinct volumes: localfield ~ N(0, 0.05²); totalfield adds an
    independent background of the same scale (in-mask corr ≈ 0.72 with localfield); chimap is half
    the localfield plus independent noise (≈ 0.54 with localfield, ≈ 0.37 with totalfield);
    chimap-sti is a further perturbation of chimap (≈ 0.50 with localfield). Outside the
    central-cube mask the χ maps are sign-flipped, so a whole-volume correlation differs sharply
    from the in-mask one (localfield vs chimap: ≈ −0.33 unmasked)."""
    rng = np.random.default_rng(0)
    lf = rng.standard_normal(SHAPE) * 0.05
    tf = lf + rng.standard_normal(SHAPE) * 0.05
    chi = 0.5 * lf + rng.standard_normal(SHAPE) * 0.05
    sti = 0.9 * chi + rng.standard_normal(SHAPE) * 0.02
    mask = np.zeros(SHAPE, "float32")
    mask[4:12, 4:12, 4:12] = 1.0
    outside = mask == 0
    chi[outside] *= -1
    sti[outside] *= -1
    v = {"totalfield": tf, "localfield": lf, "chimap": chi, "chimap-sti": sti, "mask": mask}
    return {k: a.astype("float32") for k, a in v.items()}


def _dataset(root: Path, *, sti: bool = False) -> dict:
    """Write the fixture dataset under `root`; returns its volumes (for computing expected scores).
    With sti=True also writes the second reference (chimap-sti) for the in-vivo path."""
    v = _volumes()
    _save(root / "inputs" / "mask.nii.gz", v["mask"])
    (root / "inputs" / "params.json").write_text(
        json.dumps({"TE": [0.004], "B0": 3.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
    for name in ("totalfield", "localfield", "chimap"):
        _save(root / "groundtruth" / f"{name}.nii.gz", v[name])
    if sti:
        _save(root / "groundtruth" / "chimap-sti.nii.gz", v["chimap-sti"])
    return v


def _corr(v: dict, recon: str, truth: str, mask=None) -> float:
    """What a copy of `recon` must score against `truth`, over the dataset mask by default."""
    return qsm_eval.correlation(v[recon], v[truth], v["mask"] if mask is None else mask)


def test_fixture_volumes_are_distinct_and_the_mask_matters():
    """The property every assertion below leans on: each artifact/truth pairing has its own
    correlation, none of them ~1, and scoring without the mask gives yet another number."""
    v = _volumes()
    in_mask = {("localfield", "chimap"): _corr(v, "localfield", "chimap"),
               ("totalfield", "chimap"): _corr(v, "totalfield", "chimap"),
               ("totalfield", "localfield"): _corr(v, "totalfield", "localfield")}
    assert all(0.1 < c < 0.9 for c in in_mask.values()), in_mask
    vals = sorted(in_mask.values())
    assert all(b - a > 0.05 for a, b in zip(vals, vals[1:])), in_mask
    assert abs(_corr(v, "localfield", "chimap", np.ones(SHAPE)) - in_mask[("localfield", "chimap")]) > 0.3


def _run(dataset: Path, runs_out: Path, work: Path, *, mode: str, track: str, include: str,
         extra: tuple = (), env_extra: "dict | None" = None) -> list:
    env = {**os.environ, "QSMCI_ALGORITHMS_DIR": str(METHODS), **(env_extra or {})}
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pipeline.py"),
         "--dataset", str(dataset), "--mode", mode, "--runner", "local", "--track", track,
         "--include", include, "--runs-out", str(runs_out), "--work", str(work), *extra],
        cwd=str(ROOT), env=env, check=True)
    return json.loads(runs_out.read_text())


def test_isolated_dipole_scores(tmp_path):
    v = _dataset(tmp_path / "ds")
    runs = _run(tmp_path / "ds", tmp_path / "runs.json", tmp_path / "work",
                mode="isolated", track="sim", include="cp-method")
    cp = [r for r in runs if r["slug"] == "cp-method"]
    assert cp, "cp-method isolated dipole run missing"
    r = cp[0]
    assert r["status"] == "ok" and r["artifact"] == "chimap"
    # cp-method copies the GT localfield it was fed, scored against the GT chimap over the mask
    assert r["metrics"]["correlation"] == pytest.approx(_corr(v, "localfield", "chimap"), abs=TOL)
    assert "hfen" in r["metrics"]              # in-vivo/no-seg chi metric set includes HFEN


def test_composed_matrix_runs(tmp_path):
    v = _dataset(tmp_path / "ds")
    runs = _run(tmp_path / "ds", tmp_path / "runs.json", tmp_path / "work",
                mode="composed", track="sim", include="cp-bfr,cp-method")
    by_id = {r["id"]: r for r in runs}
    r = by_id["gt~cp-bfr~cp-method-cmp"]
    assert r["mode"] == "composed" and r["artifact"] == "chimap" and r["status"] == "ok"
    assert r["combo"] == {"field_mapping": "gt", "bfr": "cp-bfr", "dipole": "cp-method"}
    # gt totalfield -> cp-bfr (copy) -> cp-method (copy): the chimap IS the gt totalfield, so the
    # score is corr(totalfield, chimap) — not corr(localfield, chimap), which a dipole wired straight
    # to the GT localfield (skipping the bfr output) would produce.
    assert r["metrics"]["correlation"] == pytest.approx(_corr(v, "totalfield", "chimap"), abs=TOL)
    assert r["metrics"]["correlation"] != pytest.approx(_corr(v, "localfield", "chimap"), abs=0.05)


def test_phantom_namespacing(tmp_path):
    """--phantom on a NON-default phantom must suffix run ids with -<phantom-id> and stamp the rows
    with a `phantom` field, while the track's default phantom keeps the bare legacy ids — the
    contract that lets several phantoms of one track coexist in results/index.json."""
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    reg["sim-alt"] = {"track": "sim", "label": "Alt phantom", "osf_file": "x",
                      "path": "data/sim-alt/scoring", "active": True}
    regfile = tmp_path / "datasets.json"
    regfile.write_text(json.dumps(reg))
    env = {"QSMCI_DATASETS_FILE": str(regfile)}
    v = _dataset(tmp_path / "ds")
    expected = _corr(v, "localfield", "chimap")

    # non-default phantom: namespaced ids + phantom field
    runs = _run(tmp_path / "ds", tmp_path / "runs-alt.json", tmp_path / "work-alt",
                mode="isolated", track="sim", include="cp-method",
                extra=("--phantom", "sim-alt"), env_extra=env)
    r = next(r for r in runs if r["slug"] == "cp-method")
    assert r["id"].endswith("-sim-alt") and r["phantom"] == "sim-alt"
    assert r["metrics"]["correlation"] == pytest.approx(expected, abs=TOL)

    # default phantom: legacy bare ids, but the phantom field is still stamped
    runs = _run(tmp_path / "ds", tmp_path / "runs-def.json", tmp_path / "work-def",
                mode="isolated", track="sim", include="cp-method",
                extra=("--phantom", "sim"), env_extra=env)
    r = next(r for r in runs if r["slug"] == "cp-method")
    assert r["id"] == "cp-method-iso" and r["phantom"] == "sim"
    assert r["metrics"]["correlation"] == pytest.approx(expected, abs=TOL)


def test_invivo_two_reference_scoring(tmp_path):
    v = _dataset(tmp_path / "ds", sti=True)
    runs = _run(tmp_path / "ds", tmp_path / "runs.json", tmp_path / "work",
                mode="isolated", track="invivo", include="cp-method")
    cp = [r for r in runs if r["slug"] == "cp-method"]
    assert cp, "cp-method invivo run missing"
    r = cp[0]
    assert r["track"] == "invivo" and r["id"].endswith("-invivo")
    # primary (COSMOS-equivalent) + secondary (STI) metrics both present, each against ITS reference
    assert r["metrics"]["correlation"] == pytest.approx(_corr(v, "localfield", "chimap"), abs=TOL)
    assert r["metrics"]["correlation_sti"] == pytest.approx(_corr(v, "localfield", "chimap-sti"), abs=TOL)
    assert "nrmse" in r["metrics"] and "nrmse_sti" in r["metrics"]


def test_missing_artifact_is_a_dnf_row_not_an_abort(tmp_path):
    """A method wanting an artifact the dataset lacks used to raise SystemExit out of every per-run
    guard and kill the whole invocation. It must be ONE DNF row (with the reason) while the other
    methods in the same run still score."""
    _dataset(tmp_path / "ds")   # ships no magnitude
    runs = _run(tmp_path / "ds", tmp_path / "runs.json", tmp_path / "work",
                mode="isolated", track="sim", include="cp-method,needs-magnitude")
    by_id = {r["id"]: r for r in runs}
    assert by_id["needs-magnitude-iso"]["status"] == "DNF"
    assert "magnitude" in by_id["needs-magnitude-iso"]["dnf_reason"]
    assert by_id["cp-method-iso"]["status"] == "ok"


def test_upstream_bfr_failure_records_its_pipelines_as_dnf(tmp_path):
    """A BFR that fails in the composed matrix must leave a DNF row for every pipeline built on it
    (so a re-score replaces the old score instead of leaving a stale 'ok'), while pipelines on the
    healthy BFR still score."""
    _dataset(tmp_path / "ds")
    runs = _run(tmp_path / "ds", tmp_path / "runs.json", tmp_path / "work",
                mode="composed", track="sim", include="cp-bfr,fail-bfr,cp-method")
    by_id = {r["id"]: r for r in runs}
    bad = by_id["gt~fail-bfr~cp-method-cmp"]
    assert bad["status"] == "DNF" and bad["stage"] == "bfr+dipole"
    assert "upstream bfr fail-bfr" in bad["dnf_reason"]
    assert bad["combo"] == {"field_mapping": "gt", "bfr": "fail-bfr", "dipole": "cp-method"}
    assert by_id["gt~cp-bfr~cp-method-cmp"]["status"] == "ok"
