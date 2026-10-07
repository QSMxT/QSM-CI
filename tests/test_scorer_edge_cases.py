"""PINNED behaviour of the scorer's degenerate inputs — what it does today, not what it should do.

An empty mask and a constant (flat) reconstruction both reach code paths where "the score" is not
defined, and `eval/qsm_eval.py` answers them inconsistently: an empty mask gives `correlation` 0.0
and `xsim` 0.0 but `hfen` NaN and `nrmse_challenge` (NaN, NaN). That matters downstream, because 0.0
is a legitimate score the leaderboard will rank while NaN is dropped as "not scored" — so the same
degenerate run is ranked by two metrics and omitted by two others.

These tests exist to pin that behaviour so it cannot drift silently; they deliberately do NOT assert
the consistent behaviour. Making the four agree (all-NaN, or all-sentinel) is a scoring-policy
decision for the maintainer, tracked on issue #235, and would change published numbers. If that
decision is taken, these expectations are what should be updated with it.

Imported as `from qsm_ci import qsm_eval`, the same path the rest of tests/ uses (the module is the
symlinked twin of eval/qsm_eval.py, which `eval/test_metrics.py` imports directly as `qsm_eval`).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from qsm_ci import qsm_eval as qe

SHAPE = (8, 8, 8)


@pytest.fixture
def truth():
    """A random χ-like volume; nothing about these pins depends on its content, only on its being
    non-constant (so the truth norms the metrics divide by are non-zero)."""
    return np.random.default_rng(0).standard_normal(SHAPE).astype("float32")


@pytest.fixture
def recon():
    return np.random.default_rng(1).standard_normal(SHAPE).astype("float32")


@pytest.fixture
def empty_mask():
    return np.zeros(SHAPE, dtype=bool)


@pytest.fixture
def full_mask():
    return np.ones(SHAPE, dtype=bool)


# ------------------------------------------------------------------- an empty mask: 0.0 vs NaN


def test_an_empty_mask_scores_correlation_as_zero_not_nan(recon, truth, empty_mask):
    """0.0 is the "no linear relationship" sentinel — indistinguishable from a real zero correlation."""
    assert qe.correlation(recon, truth, empty_mask) == 0.0


def test_an_empty_mask_scores_xsim_as_zero_not_nan(recon, truth, empty_mask):
    """Same sentinel as correlation: xsim returns 0.0 when no window is valid."""
    assert qe.xsim(recon, truth, empty_mask) == 0.0


def test_an_empty_mask_scores_hfen_as_nan(recon, truth, empty_mask):
    """Inconsistent with correlation/xsim above, and pinned as such (issue #235)."""
    assert math.isnan(qe.hfen(recon, truth, empty_mask))


def test_an_empty_mask_scores_both_nrmse_variants_as_nan(recon, truth, empty_mask):
    plain, detrended = qe.nrmse_challenge(recon, truth, empty_mask)
    assert math.isnan(plain) and math.isnan(detrended)


def test_the_empty_mask_sentinels_are_still_split_two_and_two(recon, truth, empty_mask):
    """The inconsistency itself, asserted in one place so a future policy change trips exactly one
    expectation that names the decision instead of four scattered ones."""
    finite = {
        "correlation": qe.correlation(recon, truth, empty_mask),
        "xsim": qe.xsim(recon, truth, empty_mask),
    }
    nan = {
        "hfen": qe.hfen(recon, truth, empty_mask),
        "nrmse": qe.nrmse_challenge(recon, truth, empty_mask)[0],
    }
    assert all(v == 0.0 for v in finite.values()), finite
    assert all(math.isnan(v) for v in nan.values()), nan


# ------------------------------------------------- a constant recon: the do-nothing baseline


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_has_zero_correlation(truth, full_mask, value):
    """A flat map has zero variance, so Pearson's denominator is 0 and the guard returns 0.0 — the
    same value a genuinely uncorrelated recon gets. Any constant scores alike."""
    const = np.full(SHAPE, value, dtype="float32")
    assert qe.correlation(const, truth, full_mask) == 0.0


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_scores_xsim_at_essentially_zero(truth, full_mask, value):
    """NOT the 0.0 sentinel: the windows are valid (den > 0 thanks to c2), so this is a computed
    score — the covariance term is ~0 for a flat map, leaving a tiny signed residue on either side of
    zero. Pinned as a magnitude, since the exact value depends on scipy's uniform_filter rounding."""
    const = np.full(SHAPE, value, dtype="float32")
    assert abs(qe.xsim(const, truth, full_mask)) < 1e-4


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_scores_hfen_at_one_hundred_percent(truth, full_mask, value):
    """LoG kills a constant, so the error norm equals the truth's own norm: 100% = "recovered none of
    the fine detail", the do-nothing baseline."""
    const = np.full(SHAPE, value, dtype="float32")
    assert qe.hfen(const, truth, full_mask) == pytest.approx(100.0, abs=1e-6)


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_scores_both_nrmse_variants_at_one_hundred_percent(truth, full_mask, value):
    """Demeaning makes the recon all-zero, so plain NRMSE is the 100% do-nothing baseline. The
    DETRENDED variant does not rescue it: the fitted slope is 0, which trips the `abs(slope) < 1e-30`
    guard and returns the plain value rather than dividing by zero."""
    const = np.full(SHAPE, value, dtype="float32")
    plain, detrended = qe.nrmse_challenge(const, truth, full_mask)
    assert plain == pytest.approx(100.0, abs=1e-6)
    assert detrended == plain


# ------------------------------------------------------ a constant truth: nothing to score against


@pytest.mark.parametrize("value", [0.5, -2.0, 0.0])
def test_a_constant_truth_scores_both_nrmse_variants_as_nan(recon, full_mask, value):
    """The mirror case: a flat TRUTH demeans to all zeros, so there is nothing to normalise by and
    the `norm_truth < 1e-30` guard returns NaN for both variants."""
    const_truth = np.full(SHAPE, value, dtype="float32")
    plain, detrended = qe.nrmse_challenge(recon, const_truth, full_mask)
    assert math.isnan(plain) and math.isnan(detrended)


def test_a_constant_truth_scores_hfen_as_nan_only_when_the_constant_is_exactly_zero(recon, full_mask):
    """HFEN's guard is on the LoG of the truth, and that is only EXACTLY zero for an all-zero volume.
    For any other constant, float32 rounding leaves a LoG floor around 1e-8 that clears the 1e-30
    guard, so the ratio comes back finite and absurd (tens of millions of percent) instead of NaN.
    Pinned because it is a NaN-vs-huge-number split on the same degenerate input (issue #235)."""
    zero_truth = np.zeros(SHAPE, dtype="float32")
    assert math.isnan(qe.hfen(recon, zero_truth, full_mask))

    flat_truth = np.full(SHAPE, 0.5, dtype="float32")
    val = qe.hfen(recon, flat_truth, full_mask)
    assert math.isfinite(val) and val > 1e3        # not a score; a divide-by-rounding-floor artefact


@pytest.mark.parametrize("value", [0.5, -2.0, 0.0])
def test_a_constant_truth_has_zero_correlation(recon, full_mask, value):
    const_truth = np.full(SHAPE, value, dtype="float32")
    assert qe.correlation(recon, const_truth, full_mask) == 0.0
