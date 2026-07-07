"""Guards for the qsm-eval metric port.

Run with `pytest eval/test_metrics.py`. These pin the invariants that must hold for the port to
stay faithful to the QSM.rs reference; extend with fixtures cross-checked against QSM.rs numbers on
real phantom data as the challenge dataset is finalized.
"""

import numpy as np

import qsm_eval as qe


def test_identity_is_perfect():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((20, 20, 20)) * 0.05
    mask = np.ones_like(x, dtype=np.uint8)
    assert abs(qe.correlation(x, x, mask) - 1.0) < 1e-9
    assert abs(qe.xsim(x, x, mask) - 1.0) < 1e-6
    n, ndt = qe.nrmse_challenge(x, x, mask)
    assert abs(n) < 1e-9 and abs(ndt) < 1e-9


def test_nrmse_detrend_removes_linear_scaling():
    rng = np.random.default_rng(1)
    truth = rng.standard_normal((16, 16, 16)) * 0.05
    mask = np.ones_like(truth, dtype=np.uint8)
    recon = 2.0 * truth + 0.01  # pure linear bias
    n, ndt = qe.nrmse_challenge(recon, truth, mask)
    assert ndt < 1e-6 < n  # detrending recovers a near-perfect match


def test_dilate_matches_cube():
    m = np.zeros((5, 5, 5), np.uint8)
    m[2, 2, 2] = 1
    d = qe.dilate_mask_3d(m)
    assert d[1:4, 1:4, 1:4].sum() == 27
    assert d.sum() == 27


def test_dgm_linearity_perfect_when_equal():
    seg = np.zeros((8, 8, 8), np.uint8)
    for lbl in range(1, 7):
        seg.flat[lbl * 10 : lbl * 10 + 5] = lbl
    x = np.linspace(-0.1, 0.1, seg.size).reshape(seg.shape)
    assert qe.dgm_linearity(x, x, seg) < 1e-9
