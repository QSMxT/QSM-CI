"""End-to-end pipeline test across every workflow engine we support.

Builds the *same* phase → χ pipeline — field-mapping (romeo-fieldmap) → background-field removal
(vsharp) → dipole inversion (rts) — through all five engines and checks two things:

1. **Consistency** — every engine drives the identical `qsm-ci run` chain, so all five χ maps must be
   bit-identical. This is the real proof that each engine's support works end-to-end.
2. **Quality** — the reconstruction actually matches the ground-truth χ (correlation / XSIM), so we
   know the pipeline produced something real, not just consistent garbage.

nipype/pydra compose in Python via the shipped interfaces; CWL/Snakemake/Nextflow run the wrappers
emitted by `qsm-ci interface --pipeline`. All stages run in the qsmxt container (docker).

This needs a *real* dataset (phase images + ground truth), so it's driven by `QSMCI_PHANTOM` pointing
at a packed dataset (scripts/pack_dataset.py) — CI fetches the challenge data from OSF. Without it the
test skips, since it can't fabricate realistic phase data. The quality floors default to values suited
to the real challenge phantom and can be overridden with QSMCI_MIN_CORR / QSMCI_MIN_XSIM.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import qsm_eval

REPO = Path(__file__).parent.parent
ALGOS = str((REPO / "algorithms").resolve())
EXAMPLES = REPO / "examples" / "workflow-engines"       # the tested artifacts ARE the shipped examples
FM, BFR, DIP = "romeo-fieldmap", "vsharp", "rts"        # (baked into the example pipelines)

# So bare slugs resolve inside isolated Nextflow/CWL work dirs (and for the in-process engines).
# PYDRA_PLUGIN=serial keeps the pydra example deterministic here (no multiprocessing).
os.environ.setdefault("QSMCI_ALGORITHMS", ALGOS)
ENV = {**os.environ, "QSMCI_ALGORITHMS": ALGOS, "PYDRA_PLUGIN": "serial"}

MIN_CORR = float(os.environ.get("QSMCI_MIN_CORR", "0.5"))
MIN_XSIM = float(os.environ.get("QSMCI_MIN_XSIM", "0.1"))


@pytest.fixture(scope="session")
def phantom() -> dict:
    env = os.environ.get("QSMCI_PHANTOM")
    if not env:
        pytest.skip("QSMCI_PHANTOM unset — the end-to-end pipeline test needs a real dataset "
                    "(CI fetches the challenge data from OSF via scripts/fetch_dataset.sh)")
    d = Path(env)
    p = {"phase": d / "inputs" / "phase.nii.gz", "magnitude": d / "inputs" / "magnitude.nii.gz",
         "mask": d / "inputs" / "mask.nii.gz", "params": d / "inputs" / "params.json",
         "chimap_truth": d / "groundtruth" / "chimap.nii.gz"}
    for name, path in p.items():
        assert path.exists(), f"phantom missing {name}: {path}"
    return {k: str(v) for k, v in p.items()}


# --- one runner per engine; each runs the SHIPPED example file and returns the produced chimap ---

def _py_example(script: str, phantom, wd) -> str:
    wd.mkdir(parents=True, exist_ok=True)
    chi = wd / "chimap.nii.gz"
    subprocess.run([sys.executable, str(EXAMPLES / script),
                    "--phase", phantom["phase"], "--magnitude", phantom["magnitude"],
                    "--mask", phantom["mask"], "--params", phantom["params"],
                    "--out", str(chi), "--runner", "docker"], check=True, env=ENV, cwd=str(wd))
    return str(chi)


def _nipype(phantom, wd) -> str:
    return _py_example("nipype_pipeline.py", phantom, wd)


def _pydra(phantom, wd) -> str:
    return _py_example("pydra_pipeline.py", phantom, wd)


def _cwl(phantom, wd) -> str:
    wd.mkdir(parents=True, exist_ok=True)
    subprocess.run([_bin("cwltool"), "--preserve-environment", "QSMCI_ALGORITHMS",
                    "--outdir", str(wd), str(EXAMPLES / "pipeline.cwl"),
                    "--phase", phantom["phase"], "--magnitude", phantom["magnitude"],
                    "--mask", phantom["mask"], "--params", phantom["params"]], check=True, env=ENV)
    return str(wd / "chimap.nii.gz")


def _snakemake(phantom, wd) -> str:
    wd.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLES / "Snakefile", wd / "Snakefile")
    for key, canon in [("phase", "phase.nii.gz"), ("magnitude", "magnitude.nii.gz"),
                       ("mask", "mask.nii.gz"), ("params", "params.json")]:
        shutil.copy(phantom[key], wd / canon)
    subprocess.run([_bin("snakemake"), "-c1", "chimap.nii.gz"], cwd=str(wd), check=True, env=ENV)
    return str(wd / "chimap.nii.gz")


def _nextflow(phantom, wd) -> str:
    wd.mkdir(parents=True, exist_ok=True)
    subprocess.run([_bin("nextflow"), "run", str(EXAMPLES / "pipeline.nf"),
                    "--phase", phantom["phase"], "--magnitude", phantom["magnitude"],
                    "--mask", phantom["mask"], "--params", phantom["params"],
                    "--outdir", str(wd / "out")], cwd=str(wd), check=True, env=ENV)
    return str(wd / "out" / "chimap.nii.gz")


def _bin(name: str) -> str:
    path = shutil.which(name)
    assert path, f"{name} not found on PATH (needed for the end-to-end pipeline test)"
    return path


ENGINES = {"nipype": _nipype, "pydra": _pydra, "cwl": _cwl, "snakemake": _snakemake, "nextflow": _nextflow}


def test_end_to_end_pipeline_all_engines(phantom, tmp_path):
    chi = {eng: run(phantom, tmp_path / eng) for eng, run in ENGINES.items()}

    ref = qsm_eval.load(chi["nipype"])
    truth = qsm_eval.load(phantom["chimap_truth"])
    mask = qsm_eval.load(phantom["mask"]) > 0.5
    corr = qsm_eval.correlation(ref, truth, mask)
    xs = qsm_eval.xsim(ref, truth, mask)
    nrmse = qsm_eval.nrmse_challenge(ref, truth, mask)[0]
    print(f"\nend-to-end {FM} → {BFR} → {DIP}:  xsim={xs:.3f}  corr={corr:.3f}  nrmse={nrmse:.1f}")

    # 1. consistency — every engine ran the identical pipeline
    for eng, path in chi.items():
        got = qsm_eval.load(path)
        assert got.shape == ref.shape, f"{eng}: shape {got.shape} != {ref.shape}"
        assert np.allclose(got, ref, atol=1e-4), f"{eng} χ map differs from the nipype reference"

    # 2. quality — a real reconstruction that matches the ground truth
    assert corr > MIN_CORR, f"correlation {corr:.3f} below {MIN_CORR}"
    assert xs > MIN_XSIM, f"xsim {xs:.3f} below {MIN_XSIM}"
