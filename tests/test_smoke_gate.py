"""scripts/pipeline.py — the `--smoke` PR gate, and what a DNF leaves behind.

`_smoke_check`'s docstring promised a "present, correctly shaped, finite, non-empty" volume but only
ever checked presence and finiteness, so a method that ignored the crop and reconstructed at full
size — or wrote a 4D volume for a 3D artifact — passed the PR gate and only failed later against the
real ground truth. `_smoke_crop` also left the affine translation unshifted, so every cropped input's
header described a box offset from where the data actually sat.

A DNF is the other half: results/<id>/ is gitignored scratch, but a self-hosted runner reuses its
workspace, so nothing on the DNF path cleared the previous run's volumes and resource trace.
"""
from __future__ import annotations

import json

import nibabel as nib
import numpy as np
import pytest

from qsm_ci.stages import ARTIFACT_FILE

BOX = 4


def _vol(path, shape, affine=None):
    aff = np.diag([2.0, 2.0, 2.0, 1.0]) if affine is None else affine
    nib.save(nib.Nifti1Image(np.ones(shape, np.float32), aff), path)
    return aff


def _inputs(tmp_path, consumes, shape=(10, 10, 10)):
    d = tmp_path / "in"
    d.mkdir(exist_ok=True)
    for art in consumes:
        if art == "params":
            (d / ARTIFACT_FILE[art]).write_text("{}")
        elif art in ("phase", "magnitude"):
            _vol(d / ARTIFACT_FILE[art], shape + (3,))
        else:
            _vol(d / ARTIFACT_FILE[art], shape)
    return d


def test_the_crop_moves_the_affine_origin_with_the_data(pipeline, tmp_path):
    """A 10³ volume cropped to a central 4³ box starts at voxel 3, so the world origin moves by
    3 voxels along each axis. Leaving the affine alone made the header describe the wrong box."""
    idir = _inputs(tmp_path, ["mask", "params"])
    before = nib.load(idir / "mask.nii.gz").affine.copy()
    pipeline._smoke_crop(idir, ["mask", "params"], BOX)
    after = nib.load(idir / "mask.nii.gz")
    assert after.shape == (BOX, BOX, BOX)
    assert np.allclose(after.affine[:3, 3], before[:3, 3] + before[:3, :3] @ np.array([3.0, 3.0, 3.0]))
    assert np.allclose(after.affine[:3, :3], before[:3, :3])   # resolution/orientation untouched


def test_the_crop_leaves_the_echo_axis_and_small_axes_alone(pipeline, tmp_path):
    idir = _inputs(tmp_path, ["magnitude", "mask", "params"], shape=(10, 3, 10))
    pipeline._smoke_crop(idir, ["magnitude", "mask", "params"], BOX)
    assert nib.load(idir / "magnitude.nii.gz").shape == (BOX, 3, BOX, 3)  # axis of 3 < box: kept


def _algo(stage="dipole"):
    from qsm_ci.stages import STAGES, produced_artifacts
    return {"slug": "demo", "name": "Demo", "stage": stage,
            "consumes": STAGES[stage]["consumes"], "produces": produced_artifacts(stage)}


class _Args:
    track = "sim"


@pytest.mark.parametrize("shape,ok", [
    ((BOX, BOX, BOX), True),
    ((10, 10, 10), False),          # ignored the crop and reconstructed at full size
    ((BOX, BOX, BOX, 3), False),    # 4D volume for a 3D artifact
    ((BOX, BOX, 3), False),         # wrong grid entirely
])
def test_the_gate_requires_the_cropped_input_grid(pipeline, tmp_path, shape, ok):
    idir = _inputs(tmp_path, _algo()["consumes"])
    pipeline._smoke_crop(idir, _algo()["consumes"], BOX)
    odir = tmp_path / "out"
    odir.mkdir()
    _vol(odir / ARTIFACT_FILE["chimap"], shape)
    row = pipeline._smoke_check(_algo(), "", "default", odir, 1.0, _Args(), idir)
    assert (row["status"] == "ok") is ok
    if not ok:
        assert "shape" in row["dnf_reason"]


def test_the_gate_still_fails_an_empty_output(pipeline, tmp_path):
    idir = _inputs(tmp_path, _algo()["consumes"])
    pipeline._smoke_crop(idir, _algo()["consumes"], BOX)
    odir = tmp_path / "out"
    odir.mkdir()
    nib.save(nib.Nifti1Image(np.zeros((BOX, BOX, BOX), np.float32), np.eye(4)),
             odir / ARTIFACT_FILE["chimap"])
    row = pipeline._smoke_check(_algo(), "", "default", odir, 1.0, _Args(), idir)
    assert row["status"] == "DNF" and "empty" in row["dnf_reason"]


def test_brain_extraction_is_graded_against_its_magnitude_grid(pipeline, tmp_path):
    """It consumes no mask — the mask is what it produces — so the grid comes from the magnitude."""
    a = _algo("brain-extraction")
    idir = _inputs(tmp_path, a["consumes"])
    pipeline._smoke_crop(idir, a["consumes"], BOX)
    assert tuple(pipeline._reference_shape(idir, a["consumes"])) == (BOX, BOX, BOX)
    odir = tmp_path / "out"
    odir.mkdir()
    _vol(odir / ARTIFACT_FILE["mask"], (BOX, BOX, BOX))
    assert pipeline._smoke_check(a, "", "default", odir, 1.0, _Args(), idir)["status"] == "ok"


def test_a_dnf_drops_the_previous_runs_volumes_and_trace(pipeline, tmp_path, monkeypatch):
    """A self-hosted runner reuses its workspace: without this, publish_volumes.py re-uploads the
    last good run's recon and _stamp_resource_summary stamps its peak memory onto the DNF row."""
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    d = tmp_path / "results" / "demo-iso"
    d.mkdir(parents=True)
    _vol(d / "recon.nii.gz", (4, 4, 4))
    (d / "resources.json").write_text(json.dumps({"mem_peak_bytes": 9_000_000_000}))
    (d / "regions.json").write_text("{}")

    ok = {"id": "demo-iso", "status": "ok"}
    pipeline._clear_dnf_results(ok)
    pipeline._stamp_resource_summary(ok)
    assert d.exists() and ok["mem_peak_bytes"] == 9_000_000_000   # a good run keeps everything

    dnf = {"id": "demo-iso", "status": "DNF"}
    pipeline._clear_dnf_results(dnf)
    pipeline._stamp_resource_summary(dnf)
    assert not d.exists()
    assert "mem_peak_bytes" not in dnf


def test_the_smoke_gate_end_to_end(tmp_path):
    """Drive the real `--smoke` path (the PR gate) over the container-free `local` runner: a method
    that honours the crop passes, one that writes its own grid DNFs."""
    import os
    import subprocess
    import sys
    from tests.test_harness_smoke import ROOT, METHODS, _dataset

    ds = tmp_path / "ds"
    _dataset(ds)
    runs_out = tmp_path / "runs.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pipeline.py"),
         "--dataset", str(ds), "--mode", "isolated", "--runner", "local", "--track", "sim",
         "--include", "cp-method,fullsize-method", "--smoke", "--smoke-box", "8",
         "--runs-out", str(runs_out), "--work", str(tmp_path / "work")],
        cwd=str(ROOT), env={**os.environ, "QSMCI_ALGORITHMS_DIR": str(METHODS)}, check=True)

    by_slug = {r["slug"]: r for r in json.loads(runs_out.read_text())}
    assert by_slug["cp-method"]["status"] == "ok"
    assert by_slug["fullsize-method"]["status"] == "DNF"
    assert "shape" in by_slug["fullsize-method"]["dnf_reason"]


def test_flush_index_upserts_in_place(pipeline, tmp_path, monkeypatch):
    """Shared with the CI merge job: a rescore replaces a row where it sits rather than moving it
    to the end of results/index.json."""
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    idx = tmp_path / "results" / "index.json"
    idx.parent.mkdir(parents=True)
    idx.write_text(json.dumps({"runs": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}))
    pipeline.flush_index([{"id": "b", "status": "ok", "metrics": {}}, {"id": "z", "status": "ok"}])
    assert [r["id"] for r in json.loads(idx.read_text())["runs"]] == ["a", "b", "c", "z"]
