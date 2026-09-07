"""Every run is scored over the FULL brain mask, and `coverage` says how much of it the method filled.

Scoring used to be restricted to the recon's own non-zero support, so a method could erode the brain
edge for free. Now a dropped (zero) or failed (NaN/inf) voxel counts as error against the truth there,
which is what makes a method that covers the brain beat an equally accurate one that erodes it. These
drive eval/qsm_eval.py end to end on tiny volumes and pin that policy.
"""
import json
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"


def _save(path: Path, arr: np.ndarray) -> Path:
    nib.save(nib.Nifti1Image(np.asarray(arr, dtype="float32"), np.eye(4)), str(path))
    return path


def _score(tmp: Path, recon: np.ndarray, truth: np.ndarray, mask: np.ndarray, kind: str = "chi") -> dict:
    out = tmp / "score.json"
    subprocess.run([sys.executable, str(EVAL), "--recon", str(_save(tmp / "recon.nii.gz", recon)),
                    "--truth", str(_save(tmp / "truth.nii.gz", truth)),
                    "--mask", str(_save(tmp / "mask.nii.gz", mask)),
                    "--kind", kind, "--out", str(out)], check=True, capture_output=True)
    return json.loads(out.read_text())["metrics"]


@pytest.fixture
def phantom():
    rng = np.random.default_rng(0)
    truth = rng.normal(0, 0.05, size=(14, 14, 14))
    mask = np.zeros_like(truth, dtype=bool)
    mask[2:-2, 2:-2, 2:-2] = True
    return truth, mask


def test_perfect_recon_scores_perfectly_with_full_coverage(tmp_path, phantom):
    truth, mask = phantom
    m = _score(tmp_path, truth * mask, truth, mask)
    assert m["coverage"] == 1.0
    assert m["xsim"] > 0.999 and m["nrmse"] < 1e-3 and m["correlation"] > 0.999


def test_eroding_the_rim_lowers_the_score_and_coverage(tmp_path, phantom):
    """The same perfect values with a one-voxel rim dropped (the way SHARP-family BFRs erode) must
    score WORSE than the un-eroded map, not identically — erosion is no longer free."""
    truth, mask = phantom
    eroded = np.zeros_like(mask)
    eroded[3:-3, 3:-3, 3:-3] = True
    (tmp_path / "full").mkdir()
    (tmp_path / "eroded").mkdir()
    m_full = _score(tmp_path / "full", truth * mask, truth, mask)
    m_eroded = _score(tmp_path / "eroded", truth * eroded, truth, mask)
    assert m_eroded["coverage"] < m_full["coverage"] == 1.0
    assert m_eroded["xsim"] < m_full["xsim"]
    assert m_eroded["nrmse"] > m_full["nrmse"]


def test_non_finite_voxels_are_scored_as_missing_not_fatal(tmp_path, phantom):
    """A NaN patch inside the mask counts as error (like erosion) instead of poisoning every metric."""
    truth, mask = phantom
    recon = (truth * mask).copy()
    recon[5:8, 5:8, 5:8] = np.nan
    m = _score(tmp_path, recon, truth, mask)
    assert all(v is not None and np.isfinite(v) for v in m.values()), m
    assert m["coverage"] < 1.0
    assert m["xsim"] < 0.999


def test_empty_output_has_zero_coverage(tmp_path, phantom):
    truth, mask = phantom
    m = _score(tmp_path, np.full(truth.shape, np.nan), truth, mask)
    assert m["coverage"] == 0.0


def test_field_kind_reports_coverage_too(tmp_path, phantom):
    truth, mask = phantom
    m = _score(tmp_path, truth * mask, truth, mask, kind="field")
    assert m["coverage"] == 1.0 and "nrmse" in m and "xsim" in m


# --- per-region quantification: linearity, R² and bias across regions (issue #186) ---------------

def _seg(shape=(14, 14, 14)):
    """Six labelled blocks, big enough to clear region_stats' min_vox."""
    seg = np.zeros(shape, "int32")
    for i in range(6):
        seg[2:-2, 2:-2, 2 + i * 2:4 + i * 2] = i + 1
    return seg


def _regions(recon, truth, seg, mask):
    from importlib import import_module
    import sys
    sys.path.insert(0, str(ROOT / "eval"))
    qe = import_module("qsm_eval")
    return qe.region_regression(recon, truth, seg, mask)


def test_region_regression_is_perfect_for_an_exact_recon():
    seg = _seg()
    mask = seg > 0
    rng = np.random.default_rng(2)
    truth = np.zeros(seg.shape)
    for lab in range(1, 7):                      # a distinct mean per region, plus texture
        truth[seg == lab] = 0.02 * lab + rng.normal(0, 0.002, (seg == lab).sum())
    m = _regions(truth, truth, seg, mask)
    assert m["region_linearity"] < 1e-9 and m["region_r2"] > 0.999
    assert abs(m["region_bias"]) < 1e-9


def test_region_regression_catches_a_global_scale_error_that_xsim_would_forgive():
    """A recon at 80% of truth everywhere: perfectly correlated (R² = 1) but slope 0.8 and a
    negative bias — the failure this metric exists to surface."""
    seg = _seg()
    mask = seg > 0
    truth = np.zeros(seg.shape)
    for lab in range(1, 7):
        truth[seg == lab] = 0.02 * lab
    m = _regions(0.8 * truth, truth, seg, mask)
    assert m["region_linearity"] == pytest.approx(0.2, abs=1e-6)
    assert m["region_r2"] > 0.999          # still perfectly linear, just mis-scaled
    assert m["region_bias"] < 0            # systematic under-estimation


def test_region_r2_collapses_when_regional_values_do_not_track_the_truth():
    seg = _seg()
    mask = seg > 0
    rng = np.random.default_rng(3)
    truth = np.zeros(seg.shape)
    for lab in range(1, 7):
        truth[seg == lab] = 0.02 * lab
    recon = np.zeros(seg.shape)
    for lab in range(1, 7):                      # region means unrelated to the truth's ordering
        recon[seg == lab] = rng.permutation([0.10, 0.01, 0.07, 0.02, 0.09, 0.03])[lab - 1]
    assert _regions(recon, truth, seg, mask)["region_r2"] < 0.5


def test_region_metrics_reach_the_scored_output(tmp_path, phantom):
    """The three keys ride out of the scorer on the χ path whenever a segmentation is given."""
    truth, mask = phantom
    seg = _seg(truth.shape)
    out = tmp_path / "score.json"
    subprocess.run([sys.executable, str(EVAL),
                    "--recon", str(_save(tmp_path / "r.nii.gz", truth * mask)),
                    "--truth", str(_save(tmp_path / "t.nii.gz", truth)),
                    "--mask", str(_save(tmp_path / "m.nii.gz", mask)),
                    "--seg", str(_save(tmp_path / "s.nii.gz", seg)),
                    "--kind", "chi", "--out", str(out)], check=True, capture_output=True)
    metrics = json.loads(out.read_text())["metrics"]
    assert {"region_linearity", "region_r2", "region_bias"} <= set(metrics)
