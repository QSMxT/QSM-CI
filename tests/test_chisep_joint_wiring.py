"""χ-separation split/total error and leakage: wiring only (the maths is in eval/test_metrics.py).

pipeline._chisep_joint reads a run's two source maps, both ground-truth sources, the brain mask and
dseg from disk and hands them to qsm_eval.chisep_joint_metrics; rescore_chisep.score_pair rebuilds a
row's full χ-sep metric set from stored maps. Both must produce the same keys and numbers the scorer
does, on tiny volumes.
"""
from __future__ import annotations

import importlib
import math
from pathlib import Path

import nibabel as nib
import numpy as np

from qsm_ci import qsm_eval

SHAPE = (10, 10, 10)
JOINT = {"split_rms", "total_rms", "split_rms_rw", "total_rms_rw", "para_leak", "dia_leak",
         "dia_fe_excess", "para_wm_excess", "para_calc_excess"}


def _save(path: Path, arr) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.asarray(arr, "float32"), np.eye(4)), str(path))


def _dataset(root: Path):
    rng = np.random.default_rng(0)
    seg = np.zeros(SHAPE)
    seg[:5], seg[5:] = 2, 8
    para = 0.1 * (seg == 2) + 0.01 * rng.random(SHAPE)
    dia = 0.03 * (seg == 8) + 0.01 + 0.005 * rng.random(SHAPE)
    _save(root / "groundtruth" / "chi-para.nii.gz", para)
    _save(root / "groundtruth" / "chi-dia.nii.gz", dia)
    _save(root / "groundtruth" / "dseg.nii.gz", seg)
    _save(root / "inputs" / "mask.nii.gz", np.ones(SHAPE))
    return para, dia


def test_pipeline_joint_metrics_reach_the_row(tmp_path, pipeline):
    para, dia = _dataset(tmp_path / "ds")
    out = tmp_path / "out"
    _save(out / "chi-para.nii.gz", para + 0.004)      # a pure swap: split 4 ppb, total 0
    _save(out / "chi-dia.nii.gz", dia + 0.004)
    j = pipeline._chisep_joint(out, tmp_path / "ds" / "groundtruth", tmp_path / "ds" / "inputs" / "mask.nii.gz")
    assert set(j) == JOINT
    assert abs(j["split_rms"] - 4.0) < 1e-3 and abs(j["total_rms"]) < 1e-3
    assert abs(j["dia_fe_excess"] - 4.0) < 1e-3
    assert math.isnan(j["para_calc_excess"])       # no calcification label


def test_pipeline_joint_metrics_none_when_a_map_is_missing(tmp_path, pipeline):
    _dataset(tmp_path / "ds")
    (tmp_path / "out").mkdir()
    assert pipeline._chisep_joint(tmp_path / "out", tmp_path / "ds" / "groundtruth",
                                  tmp_path / "ds" / "inputs" / "mask.nii.gz") is None


def test_rescore_pair_matches_the_scorer(tmp_path):
    rc = importlib.import_module("rescore_chisep")
    _dataset(tmp_path / "ds")
    t = rc.load_truth(tmp_path / "ds")
    para, dia = t["para"], t["dia"]   # as read back from disk (float32 on disk)
    rp, rd = para * 0.9, dia * 1.1
    m = rc.score_pair(rp, rd, t)
    assert JOINT <= set(m)
    assert {"para_xsim", "dia_xsim", "para_mspe", "para_dgm_slope", "dia_dgm_slope"} <= set(m)
    assert not set(rc.RETIRED_KEYS) & set(m)
    ref, _ = qsm_eval.score_arrays(rp, para, t["mask"], "chisep", seg=t["seg"], component="para")
    assert abs(m["para_xsim"] - ref["xsim"]) < 1e-12
    jt = qsm_eval.chisep_joint_metrics(rp, rd, para, dia, t["mask"], t["seg"])
    assert abs(m["split_rms_rw"] - jt["split_rms_rw"]) < 1e-12
    assert m["para_calc_excess"] is None            # NaN is written as null, as in index.json
