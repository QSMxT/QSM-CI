"""pack_dataset.py wiring for qsm-forward χ-separation phantoms, on a tiny synthetic BIDS tree.

Checks where each qsm-forward derivative lands, not any algorithm: the signal-fitted `*_R2prime` is
the `r2prime` input, the imposed `*_desc-formula_R2prime` is a ground-truth-side reference that is
never mounted, `*_chisep.json` ships under groundtruth/, and the phantom's Dr+ is recorded in
params.json under `chisep_dr_hz_per_ppm`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "scripts" / "pack_dataset.py"
sys.path.insert(0, str(ROOT / "scripts"))
from scoring import gt_sources  # noqa: E402

SHAPE = (8, 8, 8)


def _nii(path: Path, value: float, shape=SHAPE, dtype=np.float32) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.full(shape, value, dtype), np.eye(4)), str(path))


def _bids(root: Path, relaxivity: "dict | None", formula: bool = True) -> Path:
    anat = root / "sub-1" / "anat"
    for e, te in enumerate((0.005, 0.010), start=1):
        for part, v in (("phase", 0.1 * e), ("mag", 1.0 / e)):
            _nii(anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii", v)
        (anat / f"sub-1_echo-{e}_part-phase_MEGRE.json").write_text(
            json.dumps({"EchoTime": te, "MagneticFieldStrength": 3.0}))
    d = root / "derivatives" / "qsm-forward" / "sub-1" / "anat"
    for name, v in (("Chimap", 0.01), ("Chimap-pos", 0.03), ("Chimap-neg", 0.02),
                    ("fieldmap-local", 0.005), ("mask", 1.0), ("dseg", 8.0),
                    ("R2prime", 7.0), ("R2map", 20.0), ("fibreangle", 45.0)):
        _nii(d / f"sub-1_{name}.nii", v)
    _nii(d / "sub-1_desc-wmrois_dseg.nii", 3, dtype=np.int16)
    if formula:
        _nii(d / "sub-1_desc-formula_R2prime.nii", 6.5)
    if relaxivity is not None:
        (d / "sub-1_chisep.json").write_text(json.dumps(
            {"ChiSeparationPhantom": {"b0": 3.0, "r2prime_source": "fitted"},
             "Relaxivity": relaxivity, "RelaxivityUnits": "Hz/ppm", "R2primeSource": "fitted"}))
    return root


def _pack(bids: Path, out: Path) -> None:
    subprocess.run([sys.executable, str(PACK), str(bids), str(out)], check=True,
                   capture_output=True, text=True)


def _val(path: Path) -> float:
    return float(np.asarray(nib.load(str(path)).dataobj).ravel()[0])


@pytest.fixture
def packed(tmp_path):
    out = tmp_path / "out"
    _pack(_bids(tmp_path / "bids", {"Model": "linear", "Dr": 141.7}), out)
    return out


def test_fitted_r2prime_is_the_input_and_the_formula_is_groundtruth(packed):
    assert _val(packed / "inputs" / "r2prime.nii.gz") == pytest.approx(7.0)
    assert _val(packed / "groundtruth" / "r2prime-formula.nii.gz") == pytest.approx(6.5)
    assert not (packed / "inputs" / "r2prime-formula.nii.gz").exists()


def test_formula_r2prime_is_never_a_mounted_source(packed):
    src = gt_sources(packed)
    assert src["r2prime"] == packed / "inputs" / "r2prime.nii.gz"
    assert all("r2prime-formula" not in str(p) for p in src.values())


def test_phantom_configuration_ships_under_groundtruth(packed):
    meta = json.loads((packed / "groundtruth" / "chisep.json").read_text())
    assert meta["Relaxivity"] == {"Model": "linear", "Dr": 141.7}
    assert not (packed / "inputs" / "chisep.json").exists()


def test_params_records_the_imposed_relaxivity(packed):
    params = json.loads((packed / "inputs" / "params.json").read_text())
    assert params["chisep_dr_hz_per_ppm"] == pytest.approx(141.7)
    assert params["TE"] == [0.005, 0.010] and params["B0"] == 3.0


def test_ridani_model_records_dr_pos(tmp_path):
    out = tmp_path / "out"
    _pack(_bids(tmp_path / "bids", {"Model": "ridani", "DrModel": "scaled",
                                    "DrPos": 323.5, "DrNegMax": 401.3}), out)
    params = json.loads((out / "inputs" / "params.json").read_text())
    assert params["chisep_dr_hz_per_ppm"] == pytest.approx(323.5)


def test_chisep_extras_are_carried(packed):
    assert _val(packed / "inputs" / "r2.nii.gz") == pytest.approx(20.0)
    assert _val(packed / "groundtruth" / "theta.nii.gz") == pytest.approx(45.0)
    rois = nib.load(str(packed / "groundtruth" / "wm_rois.nii.gz"))
    assert rois.get_data_dtype() == np.int16 and _val(packed / "groundtruth" / "wm_rois.nii.gz") == 3
    # the atlas must not be mistaken for the tissue segmentation
    assert _val(packed / "groundtruth" / "dseg.nii.gz") == pytest.approx(8.0)


def test_phantom_without_metadata_packs_as_before(tmp_path):
    out = tmp_path / "out"
    _pack(_bids(tmp_path / "bids", None, formula=False), out)
    params = json.loads((out / "inputs" / "params.json").read_text())
    assert "chisep_dr_hz_per_ppm" not in params
    assert not (out / "groundtruth" / "chisep.json").exists()
    assert not (out / "groundtruth" / "r2prime-formula.nii.gz").exists()
    assert _val(out / "inputs" / "r2prime.nii.gz") == pytest.approx(7.0)
