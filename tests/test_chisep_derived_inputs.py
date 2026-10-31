"""Derived χ-separation inputs: scripts/derive_chisep_inputs.py (staging, QSMxT command lines, packing)
and pipeline.py --inputs derived (which dataset dir, which χ a χ(TE) method gets, run ids). Wiring
only, on 6³ volumes; QSMxT itself never runs (subprocess is stubbed and writes its outputs)."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

dci = importlib.import_module("derive_chisep_inputs")
N = (6, 6, 6)
TE = [0.004, 0.008, 0.012]
SE_TE = [0.01, 0.03, 0.05]


def _nii(path: Path, data, dtype=np.float32):
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.asarray(data, dtype), np.eye(4)), str(path))


def _dataset(root: Path, se=True, r2=False) -> Path:
    inp = root / "inputs"
    rng = np.random.default_rng(0)
    _nii(inp / "phase.nii.gz", rng.uniform(-3, 3, N + (3,)))
    _nii(inp / "magnitude.nii.gz", rng.uniform(1, 2, N + (3,)))
    m = np.zeros(N); m[1:5, 1:5, 1:5] = 1
    _nii(inp / "mask.nii.gz", m, np.uint8)
    prm = {"TE": TE, "B0": 3.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}
    if se:
        _nii(inp / "se_magnitude.nii.gz", rng.uniform(1, 2, N + (3,)))
        prm.update(se_TE=SE_TE, se_TR=1.5)
    if r2:
        _nii(inp / "r2.nii.gz", np.full(N, 10.0))
    (inp / "params.json").write_text(json.dumps(prm))
    _nii(root / "groundtruth" / "chi-para.nii.gz", np.zeros(N))
    return root


def test_stage_bids_writes_one_nifti_and_sidecar_per_echo(tmp_path):
    ds = _dataset(tmp_path / "ds")
    staged = dci.stage_bids(ds, tmp_path / "bids")
    anat = tmp_path / "bids" / "sub-1" / "anat"
    assert staged == {"echoes": 3, "se_echoes": 3}
    for e, te in enumerate(TE, 1):
        for part in ("phase", "mag"):
            f = anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii"
            assert nib.load(str(f)).shape == N
            meta = json.loads(f.with_suffix(".json").read_text())
            assert meta["EchoTime"] == te and meta["MagneticFieldStrength"] == 3.0
    for e, te in enumerate(SE_TE, 1):
        assert json.loads((anat / f"sub-1_echo-{e}_part-mag_MESE.json").read_text())["EchoTime"] == te
    # the brain mask is offered to QSMxT as a qsm-forward derivative (--use-custom-masks qsm-forward)
    m = tmp_path / "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"
    assert np.asarray(nib.load(str(m)).dataobj).sum() == 64


def test_stage_bids_needs_se_echo_times(tmp_path):
    ds = _dataset(tmp_path / "ds")
    prm = json.loads((ds / "inputs/params.json").read_text()); prm.pop("se_TE")
    (ds / "inputs/params.json").write_text(json.dumps(prm))
    with pytest.raises(SystemExit, match="se_TE"):
        dci.stage_bids(ds, tmp_path / "bids")


def test_commands_with_spin_echoes(tmp_path):
    q = ["qsmxt"]
    cmds = dci.commands(q, tmp_path / "bids", tmp_path / "w", {"echoes": 3, "se_echoes": 3},
                        {"TE": TE, "se_TE": SE_TE}, None)
    run_a, run_b, r2, r2p = cmds
    assert run_a[:2] == ["qsmxt", "run"] and "--do-r2starmap" in run_a and "--use-custom-masks" in run_a
    assert "--qsm-per-echo" in run_b and run_b[run_b.index("--qsm-algorithm") + 1] == "star"
    assert run_b[run_b.index("--unwrapping-algorithm") + 1] == "laplacian"
    # R2 is the spin echoes' mono-exponential fit: the inputs come BEFORE --echo-times (greedy list)
    assert r2[1] == "r2star" and r2[2].endswith("echo-1_part-mag_MESE.nii")
    assert r2[r2.index("--echo-times") + 1:] == ["0.01", "0.03", "0.05"]
    assert r2p[1] == "r2prime" and r2p[r2p.index("--r2") + 1].endswith("R2.nii")


def test_commands_gre_only(tmp_path):
    staged = {"echoes": 3, "se_echoes": 0}
    cmds = dci.commands(["qsmxt"], tmp_path, tmp_path, staged, {"TE": TE}, tmp_path / "r2.nii.gz")
    assert [c[1] for c in cmds] == ["run", "run", "r2prime"]     # R2 is the dataset's measured map
    with pytest.raises(SystemExit, match="cannot be measured"):
        dci.commands(["qsmxt"], tmp_path, tmp_path, staged, {"TE": TE}, None)


def _fake_qsmxt(cmd, check=True):
    """Stand-in for subprocess.run: write the files each QSMxT command would."""
    k = cmd.index("qsmxt")
    cmd = cmd[k:]
    if cmd[1] == "run":
        out = Path(cmd[3]) / "derivatives/qsmxt"
        q = np.zeros(N); q[2:4, 2:4, 2:4] = 1
        _nii(out / "sub-1/anat/sub-1_desc-qsm_mask.nii", q, np.uint8)
        _nii(out / "sub-1/anat/sub-1_Chimap.nii", np.full(N, 0.1 if "--qsm-per-echo" not in cmd else 0.3))
        _nii(out / "sub-1/anat/sub-1_R2starmap.nii", np.full(N, 30.0))
        _nii(out / "workflow/sub-1/bgremove/sub-1_localfield.nii", np.full(N, 0.01))
        if "--qsm-per-echo" in cmd:
            for e in (1, 2, 10):     # sorted numerically, not as text
                _nii(out / f"sub-1/anat/sub-1_desc-echo{e}_Chimap.nii", np.full(N, float(e)))
        (out / "methods.md").write_text("methods")
    elif cmd[1] == "r2star":
        _nii(Path(cmd[cmd.index("-o") + 1]), np.full(N, 12.0))
    elif cmd[1] == "r2prime":
        _nii(Path(cmd[cmd.index("-o") + 1]), np.full(N, 18.0))


def test_main_packs_derived_inputs(tmp_path, monkeypatch):
    ds = _dataset(tmp_path / "ds")
    seen = []
    monkeypatch.setattr(dci.subprocess, "run", lambda cmd, check=True: (seen.append(cmd), _fake_qsmxt(cmd)))
    dci.main([str(ds), "--qsmxt", "apptainer exec q.sif qsmxt", "--work", str(tmp_path / "w")])
    assert seen[0][:4] == ["apptainer", "exec", "q.sif", "qsmxt"]
    out = ds / "derived" / "inputs"
    L = lambda f: np.asarray(nib.load(str(out / f)).dataobj)
    q = L("mask.nii.gz")
    assert q.sum() == 8 and q.dtype == np.uint8                      # QSMxT's reconstruction mask
    assert np.allclose(L("chimap.nii.gz")[q > 0], 0.1) and L("chimap.nii.gz")[0, 0, 0] == 0
    assert np.allclose(L("chimap-perecho.nii.gz")[q > 0], 0.3)
    assert np.allclose(L("r2prime.nii.gz")[q > 0], 18.0)
    e = L("chimap-echoes.nii.gz")
    assert e.shape == N + (3,) and list(e[3, 3, 3]) == [1.0, 2.0, 10.0]
    for f in ("phase", "magnitude", "se_magnitude"):
        assert (out / f"{f}.nii.gz").exists()
    assert json.loads((out / "params.json").read_text())["TE"] == TE
    assert os.readlink(ds / "derived" / "groundtruth") == "../groundtruth"
    assert (ds / "derived" / "groundtruth" / "chi-para.nii.gz").exists()
    assert (ds / "derived" / "methods-A.md").exists()


# ---- pipeline.py ----------------------------------------------------------------------------

def test_method_sources(pipeline, tmp_path):
    inp = tmp_path / "derived" / "inputs"; inp.mkdir(parents=True)
    src = {"chimap": inp / "chimap.nii.gz", "magnitude": inp / "magnitude.nii.gz"}
    dec = {"slug": "decompose-x", "optional": ["chimap-echoes"]}
    other = {"slug": "wavesep", "optional": []}
    assert pipeline.method_sources(src, dec, "derived") == src          # no per-echo χ: unchanged
    (inp / "chimap-perecho.nii.gz").write_bytes(b"")
    assert pipeline.method_sources(src, dec, "derived")["chimap"] == inp / "chimap-perecho.nii.gz"
    assert pipeline.method_sources(src, other, "derived") == src
    assert pipeline.method_sources(src, dec, "provided") == src


def test_use_derived_inputs(pipeline, tmp_path):
    with pytest.raises(SystemExit, match="derive_chisep_inputs.py"):
        pipeline.use_derived_inputs(tmp_path)
    (tmp_path / "derived" / "inputs").mkdir(parents=True)
    (tmp_path / "derived" / "inputs" / "params.json").write_text("{}")
    with pytest.raises(SystemExit, match="groundtruth"):
        pipeline.use_derived_inputs(tmp_path)
    (tmp_path / "groundtruth").mkdir()
    os.symlink("../groundtruth", tmp_path / "derived" / "groundtruth")
    assert pipeline.use_derived_inputs(tmp_path) == tmp_path / "derived"


def test_derived_inputs_refused_off_the_chisep_track(pipeline, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--phantom", "sim", "--inputs", "derived",
                                      "--dataset", str(tmp_path), "--mode", "isolated"])
    with pytest.raises(SystemExit, match="χ-separation phantoms"):
        pipeline.main()
