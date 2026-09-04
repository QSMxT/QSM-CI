"""Tests for the workflow-engine interfaces (qsm_ci.nipype / qsm_ci.pydra) and the `qsm-ci
interface` generator (CWL / Snakemake / Nextflow).

The interfaces just wrap `qsm-ci run <slug>`, so we exercise them against the tiny passthrough
methods in tests/methods/ (cp-bfr, cp-method) across **every runner** — docker, podman, apptainer,
and the container-free `local`. Inputs come from a qsm-forward phantom when `QSMCI_PHANTOM` points at
a packed dataset (see scripts/pack_dataset.py), otherwise the same phantom is generated here with
qsm-forward — it takes about a second, so every test runs against real physics on any machine and
nothing is skipped or stood in for.

Running this file requires the package installed (so `qsm-ci` is on PATH), the test extra
(`pip install -e ".[test]"` — nipype, pydra and qsm-forward), and the runners under test:
docker, podman and apptainer. Anything missing is a hard failure, not a skip.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

METHODS = Path(__file__).parent / "methods"
CP_BFR = str((METHODS / "cp-bfr").resolve())        # bfr:    totalfield -> localfield
CP_DIPOLE = str((METHODS / "cp-method").resolve())  # dipole: localfield -> chimap
TKD = str((Path(__file__).parent.parent / "algorithms" / "tkd-qsmrs").resolve())  # a real dipole method

RUNNERS = ["docker", "podman", "apptainer", "local"]
PACK = Path(__file__).parent.parent / "scripts" / "pack_dataset.py"


def _run(cmd: list[str], what: str) -> None:
    """Run a build step, surfacing its output if it fails — a broken phantom must be loud."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed ({' '.join(cmd)}):\n{r.stdout}\n{r.stderr}")


def _build_phantom(dest: Path) -> Path:
    """Generate the qsm-forward 'simple' phantom and pack it, exactly as CI's job does.

    qsm-forward is invoked through the *running* interpreter rather than a `qsm-forward` on PATH:
    a stale console script (one whose shebang points at a python that no longer exists) would
    otherwise shadow a perfectly good install.
    """
    if importlib.util.find_spec("qsm_forward") is None:
        raise RuntimeError(
            "qsm-forward is not installed, so the interface tests cannot build their phantom.\n"
            "Install the test extra:  pip install -e \".[test]\""
        )
    bids, packed = dest / "bids", dest / "phantom"
    _run([sys.executable, "-c", "import sys; from qsm_forward.main import main; sys.exit(main())",
          "simple", str(bids), "--resolution", "40", "40", "40", "--save-field"], "qsm-forward")
    _run([sys.executable, str(PACK), str(bids), str(packed)], "pack_dataset.py")
    return packed


@pytest.fixture(scope="session")
def phantom(tmp_path_factory) -> dict:
    """Canonical-artifact paths for a *real* qsm-forward phantom.

    Uses $QSMCI_PHANTOM when set — point it at any pack_dataset.py output to run these against a
    bigger dataset — and otherwise builds the phantom here, once per session, in about a second.
    There is deliberately no synthetic stand-in: the passthrough methods do not care what the
    voxels hold, but test_nipype_real_dipole_docker scores a genuine reconstruction against
    chimap_truth, and noise is not the field of any susceptibility distribution.
    """
    env = os.environ.get("QSMCI_PHANTOM")
    d = Path(env) if env else _build_phantom(tmp_path_factory.mktemp("qsm-forward"))
    p = {"totalfield": d / "groundtruth" / "totalfield.nii.gz",
         "localfield": d / "groundtruth" / "localfield.nii.gz",
         "chimap_truth": d / "groundtruth" / "chimap.nii.gz",
         "mask": d / "inputs" / "mask.nii.gz",
         "params": d / "inputs" / "params.json"}
    for name, path in p.items():
        assert path.exists(), f"phantom missing {name}: {path}"
    return {k: str(v) for k, v in p.items()}


def _assert_copy(out: Path, source: str) -> None:
    """The passthrough methods copy their input, so the output must match the source exactly."""
    assert out.exists(), f"{out} was not produced"
    got, src = nib.load(str(out)), nib.load(source)
    assert got.shape == src.shape, f"{got.shape} != {src.shape}"
    assert np.allclose(got.get_fdata(), src.get_fdata()), "output does not match the copied input"


# --- nipype -----------------------------------------------------------------------------------

@pytest.mark.parametrize("runner", RUNNERS)
def test_nipype_dipole(runner, phantom, tmp_path):
    from qsm_ci.nipype import DipoleInversion

    out = tmp_path / "chimap.nii.gz"
    DipoleInversion(slug=CP_DIPOLE, localfield=phantom["localfield"], mask=phantom["mask"],
                    params=phantom["params"], runner=runner, out=str(out)).run()
    _assert_copy(out, phantom["localfield"])


@pytest.mark.parametrize("runner", RUNNERS)
def test_nipype_chain_bfr_dipole(runner, phantom, tmp_path):
    """End-to-end: totalfield -> (cp-bfr) -> localfield -> (cp-method) -> chimap, wired in nipype."""
    from nipype import Node, Workflow

    from qsm_ci.nipype import BackgroundRemoval, DipoleInversion

    lf = tmp_path / "localfield.nii.gz"
    chi = tmp_path / "chimap.nii.gz"
    bfr = Node(BackgroundRemoval(slug=CP_BFR, totalfield=phantom["totalfield"], mask=phantom["mask"],
                                 params=phantom["params"], runner=runner, out=str(lf)), name="bfr")
    dip = Node(DipoleInversion(slug=CP_DIPOLE, mask=phantom["mask"], params=phantom["params"],
                               runner=runner, out=str(chi)), name="dip")
    wf = Workflow(name="chain", base_dir=str(tmp_path / "wf"))
    wf.connect(bfr, "out_file", dip, "localfield")
    wf.run()
    _assert_copy(chi, phantom["totalfield"])  # copied twice, so chimap == totalfield


def test_nipype_real_dipole_docker(phantom, tmp_path):
    """A *real* algorithm (tkd, run in the qsmxt container) through the nipype interface: it consumes
    the qsm-forward mask and produces a genuine χ map, scored against the phantom's ground truth.

    Asserts on Pearson correlation, not XSIM: XSIM's SSIM constants are tuned for the challenge χ
    dynamic range, so on the low-amplitude 'simple' phantom it reads ~0 despite a near-perfect
    reconstruction (correlation ~0.99). Correlation is scale-invariant and robust here.
    """
    from qsm_ci import qsm_eval
    from qsm_ci.nipype import DipoleInversion

    out = tmp_path / "chimap.nii.gz"
    DipoleInversion(slug=TKD, localfield=phantom["localfield"], mask=phantom["mask"],
                    params=phantom["params"], runner="docker", out=str(out)).run()
    recon = qsm_eval.load(str(out))
    truth = qsm_eval.load(phantom["chimap_truth"])
    mask = qsm_eval.load(phantom["mask"]) > 0.5
    assert out.exists() and recon.shape == truth.shape
    assert np.isfinite(recon).all() and recon.std() > 0            # a real, non-trivial reconstruction
    assert qsm_eval.correlation(recon, truth, mask) > 0.8          # actually matches the ground truth


# --- pydra ------------------------------------------------------------------------------------

@pytest.mark.parametrize("runner", RUNNERS)
def test_pydra_dipole(runner, phantom, tmp_path):
    from qsm_ci.pydra import DipoleInversion

    out = tmp_path / "chimap.nii.gz"
    task = DipoleInversion(slug=CP_DIPOLE, localfield=phantom["localfield"], mask=phantom["mask"],
                           params=phantom["params"], runner=runner, out=str(out))
    task.cache_dir = tmp_path / "cache"
    task()
    _assert_copy(out, phantom["localfield"])


# --- generator (CWL / Snakemake / Nextflow) ---------------------------------------------------

def test_generate_wrappers_cover_every_stage():
    import yaml

    from qsm_ci.interfaces import CORE_STAGES, ENGINES, generate

    for engine in ENGINES:
        text = generate(engine)
        assert text.strip(), f"{engine} produced nothing"
        for stage in CORE_STAGES:
            ident = stage.replace("+", "_").replace("-", "_")
            assert ident in text or stage in text, f"{engine} missing {stage}"
        if engine == "cwl":
            list(yaml.safe_load_all(text))  # must be valid YAML
            assert "qsm-ci" in text and "baseCommand" in text


def test_generate_single_stage_and_reject_unknown():
    from qsm_ci.interfaces import generate

    assert "localfield" in generate("snakemake", stage="bfr")
    with pytest.raises(ValueError):
        generate("does-not-exist")
    with pytest.raises(ValueError):
        generate("cwl", stage="not-a-stage")


def test_generate_pipeline_chains_stages():
    import yaml

    from qsm_ci.interfaces import generate_pipeline

    slugs = ["romeo-qsmrs", "vsharp-qsmrs", "rts-qsmrs"]
    wf = list(yaml.safe_load_all(generate_pipeline("cwl", slugs)))[0]
    assert wf["class"] == "Workflow"
    assert set(wf["steps"]) == {"field_mapping", "bfr", "dipole"}
    # the stages actually chain: each consumes the previous stage's output
    assert wf["steps"]["bfr"]["in"]["totalfield"] == "field_mapping/totalfield"
    assert wf["steps"]["dipole"]["in"]["localfield"] == "bfr/localfield"
    for engine in ("snakemake", "nextflow"):
        text = generate_pipeline(engine, slugs)
        assert all(s in text for s in slugs), f"{engine} missing a slug"
    with pytest.raises(ValueError):
        generate_pipeline("cwl", ["only-one"])  # needs exactly 3 slugs


def test_example_pipelines_are_current():
    """The checked-in examples/ declarative pipelines must match the generator (regenerate if stale)."""
    from qsm_ci.interfaces import generate_pipeline

    examples = Path(__file__).parent.parent / "examples" / "workflow-engines"
    slugs = ["romeo-qsmrs", "vsharp-qsmrs", "rts-qsmrs"]
    for fname, engine in [("pipeline.cwl", "cwl"), ("Snakefile", "snakemake"), ("pipeline.nf", "nextflow")]:
        assert (examples / fname).read_text() == generate_pipeline(engine, slugs), (
            f"{fname} is stale — regenerate: qsm-ci interface {engine} --pipeline {','.join(slugs)}")
