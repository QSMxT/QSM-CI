"""Guards for the qsm-eval metric port.

Run with `pytest eval/test_metrics.py`. These pin the invariants that must hold for the port to
stay faithful to the QSM.rs reference; extend with fixtures cross-checked against QSM.rs numbers on
real phantom data as the challenge dataset is finalized.

Identity checks (f(x, x) is perfect) are necessary but cannot catch a sign, scale, offset or mask
bug — a metric that ignored its mask, or scored -x as x, still passes them. So every metric also has
known-value checks whose expected numbers follow from its DEFINITION (in qsm_eval.py, itself the
QSM.rs port), not from running the code:

  correlation   Pearson within the mask: affine-invariant, corr(x, -x) = -1, constant -> 0.
  xsim          SSIM with L=1, K1=0.01, K2=0.001 (c1=1e-4, c2=1e-6), 5^3 windows. For a map with
                local mean mu ~ 1 and local variance v ~ 0.01 (both >> c1, c2) the luminance and
                contrast terms are (2 mu_a mu_b)/(mu_a^2 + mu_b^2) and (2 cov)/(var_a + var_b):
                b = 2a  -> (4/5) * (4/5) = 0.64;   b = a + 1  -> (4/5) * 1 = 0.8.
  nrmse         100 * |(a - mean a) - (b - mean b)| / |b - mean b| within the mask, so an offset
                costs nothing, 2b scores 100, -b scores 200 and an all-zero map scores 100 (the
                do-nothing baseline); the detrended variant divides out any slope: 0 for 2b and -b,
                and (per the slope < 1e-30 guard) equal to the plain NRMSE for a zero map.
  hfen          100 * |LoG(a) - LoG(b)| / |LoG(b)| within the mask: LoG is linear and kills a
                constant, so a + c -> 0, 2b -> 100, -b -> 200.
  dgm_linearity |1 - slope| of region means: 2b -> 1, b + c -> 0, -b -> 2.
"""

import math

import numpy as np
import pytest

import qsm_eval as qe


def _field(seed=0, shape=(20, 20, 20), scale=0.05):
    return np.random.default_rng(seed).standard_normal(shape) * scale


def _mask(shape=(20, 20, 20)):
    return np.ones(shape, dtype=np.uint8)


def _half_mask(shape=(20, 20, 20)):
    """The lower half of the volume along the first axis."""
    m = np.zeros(shape, dtype=np.uint8)
    m[: shape[0] // 2] = 1
    return m


# ------------------------------------------------------------------------------- identity


def test_identity_is_perfect():
    x = _field()
    mask = _mask()
    assert abs(qe.correlation(x, x, mask) - 1.0) < 1e-9
    assert abs(qe.xsim(x, x, mask) - 1.0) < 1e-6
    n, ndt = qe.nrmse_challenge(x, x, mask)
    assert abs(n) < 1e-9 and abs(ndt) < 1e-9
    assert abs(qe.hfen(x, x, mask)) < 1e-9


# ---------------------------------------------------------------------------- correlation


def test_correlation_sign_and_affine_invariance():
    x, mask = _field(), _mask()
    assert abs(qe.correlation(x, -x, mask) + 1.0) < 1e-9          # a sign flip is -1, not +1
    assert abs(qe.correlation(x, 2.0 * x + 0.3, mask) - 1.0) < 1e-9  # scale/offset do not matter
    assert abs(qe.correlation(x, -2.0 * x + 0.3, mask) + 1.0) < 1e-9


def test_correlation_honours_the_mask():
    """Only in-mask voxels count: a map that equals x inside the mask and -x outside is a perfect
    match within the mask, and clearly not one over the whole volume."""
    x, mask = _field(), _half_mask()
    y = np.where(mask > 0, x, -x)
    assert abs(qe.correlation(x, y, mask) - 1.0) < 1e-9
    assert abs(qe.correlation(x, y, _mask())) < 0.2   # the two halves cancel


def test_correlation_of_a_constant_is_zero_not_nan():
    """A constant map has zero variance, so the denominator vanishes: 0 by definition (the port
    lands within rounding of it — the n*sum(b^2) - sum(b)^2 form cancels to ~1e-10, not exactly 0),
    never NaN or a rounding-noise ratio. An EMPTY mask is a different question with a different
    answer — nothing to score, so NaN, which the leaderboard drops instead of ranking; see
    tests/test_scorer_edge_cases.py."""
    x, mask = _field(), _mask()
    for c in (0.3, 1.0, 0.0):
        r = qe.correlation(x, np.full_like(x, c), mask)
        assert np.isfinite(r) and abs(r) < 1e-6, (c, r)
    assert np.isnan(qe.correlation(x, x, np.zeros_like(mask)))


# ----------------------------------------------------------------------------------- xsim


def test_xsim_known_values_for_scale_and_offset():
    """mu ~ 1, v ~ 0.01 so both SSIM constants are negligible: 2a -> 0.64, a + 1 -> 0.8."""
    x = 1.0 + _field(scale=0.1)
    mask = _mask()
    assert abs(qe.xsim(x, 2.0 * x, mask) - 0.64) < 1e-3
    assert abs(qe.xsim(x, x + 1.0, mask) - 0.8) < 2e-3


def test_xsim_ordering_prefers_small_noise_to_a_wrong_scale():
    x = 1.0 + _field(scale=0.1)
    mask = _mask()
    noisy = x + _field(seed=1, scale=0.01)
    assert qe.xsim(x, 2.0 * x, mask) < qe.xsim(x, noisy, mask) < 1.0
    assert qe.xsim(x, noisy, mask) > 0.95


def test_xsim_honours_the_mask():
    """Corrupt the map only beyond the reach of any in-mask window (the mask ends at slice 10 and a
    5^3 window reaches 2 slices further, so from slice 14 on): the masked score is exactly the
    identity score, while the whole-volume score is dragged down towards the 0.64 of the 2x region."""
    x, mask = 1.0 + _field(scale=0.1), _half_mask()
    y = x.copy()
    y[14:] *= 2.0
    assert abs(qe.xsim(x, y, mask) - 1.0) < 1e-6
    assert qe.xsim(x, y, _mask()) < 0.9


# ---------------------------------------------------------------------------------- nrmse


def test_nrmse_known_values_for_offset_scale_sign_and_zero():
    truth, mask = _field(seed=1, shape=(16, 16, 16)), _mask((16, 16, 16))
    assert qe.nrmse_challenge(truth + 0.01, truth, mask) == pytest.approx((0.0, 0.0), abs=1e-6)
    assert qe.nrmse_challenge(2.0 * truth + 0.01, truth, mask) == pytest.approx((100.0, 0.0), abs=1e-6)
    assert qe.nrmse_challenge(-truth, truth, mask) == pytest.approx((200.0, 0.0), abs=1e-6)
    zero = np.zeros_like(truth)
    assert qe.nrmse_challenge(zero, truth, mask) == pytest.approx((100.0, 100.0), abs=1e-6)


def test_nrmse_honours_the_mask():
    truth, mask = _field(seed=1, shape=(16, 16, 16)), _half_mask((16, 16, 16))
    recon = np.where(mask > 0, truth, 5.0 * truth + 1.0)   # garbage outside the mask
    assert qe.nrmse_challenge(recon, truth, mask) == pytest.approx((0.0, 0.0), abs=1e-6)
    n_all, _ = qe.nrmse_challenge(recon, truth, _mask((16, 16, 16)))
    assert n_all > 50.0


# ----------------------------------------------------------------------------------- hfen


def test_hfen_known_values():
    truth, mask = _field(seed=2), _mask()
    # LoG kills a constant: the residual is the truncated (5 sigma) kernel's ~1e-5 non-zero sum,
    # so ~1e-4 % against a real field — not the tens of percent an unremoved offset would cost.
    assert abs(qe.hfen(truth + 0.01, truth, mask)) < 1e-2
    assert abs(qe.hfen(2.0 * truth, truth, mask) - 100.0) < 1e-6    # LoG is linear
    assert abs(qe.hfen(-truth, truth, mask) - 200.0) < 1e-6


# ------------------------------------------------------------------------------- dilation


def test_dilate_matches_cube():
    m = np.zeros((5, 5, 5), np.uint8)
    m[2, 2, 2] = 1
    d = qe.dilate_mask_3d(m)
    assert d[1:4, 1:4, 1:4].sum() == 27
    assert d.sum() == 27


# ---------------------------------------------------------------------------- dgm_linearity


def _seg_and_truth():
    seg = np.zeros((8, 8, 8), np.uint8)
    for lbl in range(1, 7):
        seg.flat[lbl * 10 : lbl * 10 + 5] = lbl
    x = np.linspace(-0.1, 0.1, seg.size).reshape(seg.shape)
    return seg, x


def test_dgm_linearity_perfect_when_equal():
    seg, x = _seg_and_truth()
    assert qe.dgm_linearity(x, x, seg) < 1e-9


def test_dgm_linearity_known_values():
    """|1 - slope| across the six region means: an offset is free, a scale of 2 costs 1, a sign flip
    costs 2 — and an error confined to voxels outside every DGM label costs nothing."""
    seg, x = _seg_and_truth()
    assert abs(qe.dgm_linearity(x + 0.05, x, seg)) < 1e-9
    assert abs(qe.dgm_linearity(2.0 * x, x, seg) - 1.0) < 1e-9
    assert abs(qe.dgm_linearity(-x, x, seg) - 2.0) < 1e-9
    assert abs(qe.dgm_linearity(np.where(seg > 0, x, 3.0 * x), x, seg)) < 1e-9


# ------------------------------------------------------------------ χ-separation: split vs total
#
# Synthetic two-source phantom on a 16^3 grid: four tissue classes as slabs (iron nuclei, WM,
# cortical GM, CSF), χ+ and |χ−| in ppm. Expected numbers follow from the definitions in
# qsm_eval.chisep_joint_metrics: e_split = ½(Δχ+ + Δ|χ−|), e_tot = Δχ+ − Δ|χ−|, RMS in ppb.

_SHAPE = (16, 16, 16)


def _chisep_phantom():
    seg = np.zeros(_SHAPE, np.int32)
    seg[0:4], seg[4:8], seg[8:12], seg[12:16] = 2, 8, 9, 10  # pallidus, WM, GM, CSF
    rng = np.random.default_rng(1)
    para = np.choose(np.searchsorted([2, 8, 9, 10], seg), [0.14, 0.007, 0.034, 0.03]) \
        + 0.005 * rng.random(_SHAPE)
    dia = np.choose(np.searchsorted([2, 8, 9, 10], seg), [0.014, 0.037, 0.024, 0.01]) \
        + 0.005 * rng.random(_SHAPE)
    return para, dia, seg, _mask(_SHAPE)


def test_chisep_perfect_separation_scores_zero():
    p, d, seg, m = _chisep_phantom()
    j = qe.chisep_joint_metrics(p, d, p, d, m, seg)
    for k in ("split_rms", "split_rms_rw", "total_rms", "total_rms_rw",
              "dia_fe_excess", "para_wm_excess"):
        assert abs(j[k]) < 1e-9, k
    assert abs(j["para_leak"]) < 1e-9 and abs(j["dia_leak"]) < 1e-9


def test_chisep_pure_total_error_has_no_split_error():
    """+δ on χ+ and −δ on |χ−| changes only χ+ − |χ−| (by 2δ): split 0, total 2δ."""
    p, d, seg, m = _chisep_phantom()
    delta = 0.004
    j = qe.chisep_joint_metrics(p + delta, d - delta, p, d, m, seg)
    assert abs(j["split_rms"]) < 1e-9 and abs(j["split_rms_rw"]) < 1e-9
    assert j["total_rms"] == pytest.approx(2 * delta * 1e3)
    assert j["total_rms_rw"] == pytest.approx(2 * delta * 1e3)


def test_chisep_pure_swap_is_all_split_error():
    """δ moved into BOTH χ+ and |χ−| keeps the total: split δ, total 0."""
    p, d, seg, m = _chisep_phantom()
    delta = 0.006
    j = qe.chisep_joint_metrics(p + delta, d + delta, p, d, m, seg)
    assert j["split_rms"] == pytest.approx(delta * 1e3)
    assert abs(j["total_rms"]) < 1e-9


def test_chisep_split_and_total_decompose_the_per_source_errors():
    """e+² + e−² = 2·e_split² + ½·e_tot² voxelwise, so the brain RMS obey the same identity."""
    p, d, seg, m = _chisep_phantom()
    rng = np.random.default_rng(7)
    rp, rd = p + 0.01 * rng.standard_normal(_SHAPE), d + 0.01 * rng.standard_normal(_SHAPE)
    j = qe.chisep_joint_metrics(rp, rd, p, d, m, seg)
    lhs = np.mean((rp - p) ** 2) + np.mean((rd - d) ** 2)
    assert 1e-6 * (2 * j["split_rms"] ** 2 + 0.5 * j["total_rms"] ** 2) == pytest.approx(lhs)


def test_chisep_region_weighting_gives_each_class_equal_weight():
    """An error confined to the iron slab: the brain RMS dilutes it by its voxel share, the
    region-weighted RMS by the class count (4 classes present)."""
    p, d, seg, m = _chisep_phantom()
    delta = 0.008
    rp = p + delta * (seg == 2)
    rd = d + delta * (seg == 2)           # a swap, inside the iron nuclei only
    j = qe.chisep_joint_metrics(rp, rd, p, d, m, seg)
    frac = float((seg == 2).mean())       # 4/16
    assert j["split_rms"] == pytest.approx(delta * 1e3 * np.sqrt(frac))
    assert j["split_rms_rw"] == pytest.approx(delta * 1e3 * np.sqrt(1 / 4))
    # Classes with < CHISEP_REGION_MIN_VOX voxels drop out of the weighting rather than dominating it.
    seg2 = seg.copy()
    seg2[0, 0, 0] = 11                    # a single "vein" voxel
    j2 = qe.chisep_joint_metrics(rp, rd, p, d, m, seg2)
    assert j2["split_rms_rw"] == pytest.approx(j["split_rms_rw"], rel=1e-3)


def test_chisep_regional_excess_measures_excess_over_truth():
    """False χ− in the iron nuclei / false χ+ in WM, signed, against a non-zero truth there."""
    p, d, seg, m = _chisep_phantom()
    rd = d + 0.005 * (seg == 2)
    rp = p - 0.002 * (seg == 8)
    j = qe.chisep_joint_metrics(rp, rd, p, d, m, seg)
    assert j["dia_fe_excess"] == pytest.approx(5.0)
    assert j["para_wm_excess"] == pytest.approx(-2.0)
    # the old "mean |recon|" leak would have reported the true |χ−| of the nuclei (~16 ppb) for a
    # perfect recon; the excess is 0 there
    assert abs(qe.chisep_joint_metrics(p, d, p, d, m, seg)["dia_fe_excess"]) < 1e-9


def test_chisep_calcification_metrics_hidden_without_calcification_chi():
    p, d, seg, m = _chisep_phantom()
    seg = seg.copy()
    seg[6:8, 6:8, 6:8] = 16
    # tissue-like χ in label 16 (as in the current phantoms): no calcification to score
    assert not qe.calcification_has_chi(d, seg)
    assert math.isnan(qe.chisep_joint_metrics(p, d, p, d, m, seg)["para_calc_excess"])
    md = qe.chisep_metrics(d, d, m, seg, component="dia")
    assert math.isnan(md["calc_moment_dev"]) and math.isnan(md["calc_streak"])
    # a real calcification (|χ−| 0.3 ppm) brings them back
    d2 = np.where(seg == 16, 0.3, d)
    assert qe.calcification_has_chi(d2, seg)
    assert abs(qe.chisep_joint_metrics(p, d2, p, d2, m, seg)["para_calc_excess"]) < 1e-9
    assert not math.isnan(qe.chisep_metrics(d2, d2, m, seg, component="dia")["calc_moment_dev"])


def test_chisep_region_calibration_slope_and_offset():
    """Nuclei means mapped through y = 0.8·x + 0.003 ppm → slope 0.8, offset 3 ppb."""
    seg = np.zeros(_SHAPE, np.int32)
    for i, lab in enumerate(qe.DGM_NUCLEI):
        seg[2 * i:2 * i + 2] = lab
    truth = 0.02 * seg.astype(float)
    m = _mask(_SHAPE)
    s, o = qe.region_calibration(0.8 * truth + 0.003, truth, seg, qe.DGM_NUCLEI, m > 0)
    assert s == pytest.approx(0.8) and o == pytest.approx(3.0)
    mp = qe.chisep_metrics(truth, truth, m, seg, component="para")
    assert mp["dgm_slope"] == pytest.approx(1.0) and abs(mp["dgm_offset"]) < 1e-9
    md = qe.chisep_metrics(truth, truth, m, seg, component="dia", wm_rois=seg)
    assert md["wm_slope"] == pytest.approx(1.0) and md["dgm_slope"] == pytest.approx(1.0)
    # flat truth: nothing to calibrate against
    assert all(math.isnan(v) for v in qe.region_calibration(truth, np.ones(_SHAPE), seg,
                                                            qe.DGM_NUCLEI, m > 0))


def test_chisep_joint_metrics_nothing_to_score_is_nan():
    p, d, seg, _ = _chisep_phantom()
    j = qe.chisep_joint_metrics(p, d, p, d, np.zeros(_SHAPE, np.uint8), seg)
    assert all(math.isnan(v) for v in j.values())
