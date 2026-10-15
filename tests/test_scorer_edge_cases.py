"""PINNED behaviour of the scorer's degenerate inputs.

The inconsistency these tests were written to pin (issue #235) is now RESOLVED, and the decision is
answered by CAUSE rather than by value:

  * **Nothing to score -> NaN, everywhere.** If the mask leaves no usable voxels, every metric
    returns NaN. NaN becomes JSON null in `metrics.json` and the site drops a null metric from the
    table and from every ranking, so such a run is omitted rather than ranked. Before the fix an
    empty mask gave `correlation` 0.0 and `xsim` 0.0 but `hfen` NaN and `nrmse_challenge`
    (NaN, NaN) — 0.0 being a perfectly rankable score, the same degenerate run was ranked by two
    metrics and dropped by the other two. Worse, through `score_arrays` an empty mask also earned
    `dgm_linearity` 1.0 and the BEST-POSSIBLE `calc_moment_dev` of 0.0, because those two read the
    segmentation and never saw the score mask at all.
  * **Scoreable but useless -> its real number, ranked worst.** A constant (flat) reconstruction
    under a valid mask is a genuine, measurable, bad result: correlation 0.0 (no linear relationship
    whatsoever), xsim ~0, hfen 100% and NRMSE (100, 100) — the do-nothing baseline. Those must stay
    numbers so the run ranks last; turning them into NaN would make a useless recon vanish from the
    leaderboard instead of finishing bottom of it. The expectations below are unchanged.

The guard is `qsm_eval._no_scoreable_voxels`, shared by all four metrics, and it asks for at least
two in-mask voxels that are finite in both maps (one voxel cannot support a correlation or a
demeaned norm; see the tests below).

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


def _seg():
    """A segmentation with the six DGM labels and a calcification — the labels `dgm_linearity` and
    `calcification_metrics` key off, neither of which is given the score mask."""
    seg = np.zeros(SHAPE, np.int32)
    for i, label in enumerate([1, 2, 3, 4, 5, 6, 16]):
        seg.flat[i * 10:i * 10 + 5] = label
    return seg


# ------------------------------------------------------- an empty mask: nothing to score, so NaN


def test_an_empty_mask_scores_correlation_as_nan(recon, truth, empty_mask):
    assert math.isnan(qe.correlation(recon, truth, empty_mask))


def test_an_empty_mask_scores_xsim_as_nan(recon, truth, empty_mask):
    assert math.isnan(qe.xsim(recon, truth, empty_mask))


def test_an_empty_mask_scores_hfen_as_nan(recon, truth, empty_mask):
    assert math.isnan(qe.hfen(recon, truth, empty_mask))


def test_an_empty_mask_scores_both_nrmse_variants_as_nan(recon, truth, empty_mask):
    plain, detrended = qe.nrmse_challenge(recon, truth, empty_mask)
    assert math.isnan(plain) and math.isnan(detrended)


def test_the_empty_mask_answer_is_nan_in_all_four_metrics(recon, truth, empty_mask):
    """The resolved policy, asserted in one place: no split between rankable sentinels and NaN, so a
    run with nothing to score is dropped by every metric rather than ranked by some of them."""
    scores = {
        "correlation": qe.correlation(recon, truth, empty_mask),
        "xsim": qe.xsim(recon, truth, empty_mask),
        "hfen": qe.hfen(recon, truth, empty_mask),
        "nrmse": qe.nrmse_challenge(recon, truth, empty_mask)[0],
        "nrmse_detrend": qe.nrmse_challenge(recon, truth, empty_mask)[1],
    }
    assert all(math.isnan(v) for v in scores.values()), scores


@pytest.mark.parametrize("kind,kwargs", [
    ("chi", {"seg": _seg()}),
    ("chi", {}),
    ("field", {}),
    ("chisep", {"seg": _seg(), "component": "para"}),
    ("chisep", {"seg": _seg(), "component": "dia"}),
])
def test_an_empty_mask_makes_every_published_metric_nan(recon, truth, empty_mask, kind, kwargs):
    """End to end through the scorer entry point, which is what the leaderboard publishes. Covers the
    two metrics that take `seg` and not the mask: before the fix an empty mask scored
    `dgm_linearity` 1.0 (zeroed maps fit a slope of 0, so |1 - slope| = 1) and `calc_moment_dev` 0.0
    — the best attainable value on a lower-is-better metric, for a run with nothing in it."""
    metrics, _ = qe.score_arrays(recon.astype(float), truth.astype(float),
                                 empty_mask.astype(np.uint8), kind, **kwargs)
    assert metrics, "no metrics returned at all"
    nonnan = {k: v for k, v in metrics.items() if not (isinstance(v, float) and math.isnan(v))}
    assert nonnan == {}, nonnan


# ------------------------------------------- near-empty masks: the same answer, for the same reason


def test_a_single_voxel_mask_scores_nan_everywhere(recon, truth):
    """One voxel is below the floor at which any of these statistics exists: Pearson's correlation of
    a single point is 0/0, and demeaning one voxel leaves exactly zero to normalise by. HFEN and
    xsim would still produce a number from it (both are neighbourhood filters run over the whole
    volume), but it is a number about the neighbourhood rather than a score of the brain, so the
    shared guard answers NaN for all four rather than leaving a fresh two-and-two split behind."""
    one = np.zeros(SHAPE, dtype=bool)
    one[0, 0, 0] = True
    assert math.isnan(qe.correlation(recon, truth, one))
    assert math.isnan(qe.xsim(recon, truth, one))
    assert math.isnan(qe.hfen(recon, truth, one))
    assert all(math.isnan(v) for v in qe.nrmse_challenge(recon, truth, one))


def test_two_voxels_are_enough_to_be_scored(recon, truth):
    """The guard is a floor, not a quality bar: two voxels is where the statistics start to exist, so
    they are computed and reported however ill-conditioned they look."""
    two = np.zeros(SHAPE, dtype=bool)
    two[0, 0, 0] = True
    two[0, 0, 1] = True
    assert math.isfinite(qe.correlation(recon, truth, two))
    assert math.isfinite(qe.xsim(recon, truth, two))
    assert math.isfinite(qe.hfen(recon, truth, two))
    assert all(math.isfinite(v) for v in qe.nrmse_challenge(recon, truth, two))


@pytest.mark.parametrize("which", ["recon", "truth"])
def test_a_mask_with_no_finite_values_under_it_scores_nan_everywhere(recon, truth, full_mask, which):
    """A full mask over an all-NaN map has voxels but no usable ones, so it is the same "nothing to
    score" case. Three of the four metrics used to land on NaN anyway, by propagation through their
    sums, while xsim returned the 0.0 sentinel; the shared guard makes the answer deliberate.

    Only the all-non-finite case is gated. A map with SOME non-finite voxels is still scored over the
    whole mask and propagates NaN into its score — it is not quietly scored on its good voxels only.
    (`score_arrays` zeroes non-finite recon voxels before scoring, by policy, so in the pipeline this
    case is reachable through the truth.)"""
    nan_map = np.full(SHAPE, np.nan)
    r, t = (nan_map, truth) if which == "recon" else (recon, nan_map)
    assert math.isnan(qe.correlation(r, t, full_mask))
    assert math.isnan(qe.xsim(r, t, full_mask))
    assert math.isnan(qe.hfen(r, t, full_mask))
    assert all(math.isnan(v) for v in qe.nrmse_challenge(r, t, full_mask))


def test_a_few_non_finite_voxels_still_propagate_rather_than_being_dropped(recon, truth, full_mask):
    """The complement of the test above, pinned so the guard is never mistaken for a filter: with
    enough usable voxels to clear it, a NaN left in the truth poisons the aggregate instead of being
    excluded from it."""
    dirty = truth.astype(float).copy()
    dirty[0, 0, 0] = np.nan
    assert math.isnan(qe.correlation(recon, dirty, full_mask))
    assert math.isnan(qe.nrmse_challenge(recon, dirty, full_mask)[0])


# ------------------------------------------------- a constant recon: the do-nothing baseline, RANKED


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_has_zero_correlation(truth, full_mask, value):
    """A flat map has zero variance, so Pearson's denominator is 0 and the guard returns 0.0 — the
    same value a genuinely uncorrelated recon gets. Any constant scores alike. 0.0 and not NaN is
    deliberate: the mask is valid and this is a real measurement of a useless recon, which must rank
    worst rather than be dropped."""
    const = np.full(SHAPE, value, dtype="float32")
    assert qe.correlation(const, truth, full_mask) == 0.0


@pytest.mark.parametrize("value", [0.5, 0.0, -2.0])
def test_a_constant_recon_scores_xsim_at_essentially_zero(truth, full_mask, value):
    """NOT a sentinel: the windows are valid (den > 0 thanks to c2), so this is a computed score —
    the covariance term is ~0 for a flat map, leaving a tiny signed residue on either side of zero.
    Pinned as a magnitude, since the exact value depends on scipy's uniform_filter rounding."""
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


def test_a_constant_recon_is_still_scored_end_to_end(truth, full_mask):
    """The other half of the decision, through the entry point: a useless-but-scoreable run keeps a
    full row of numbers, so it is ranked (last) rather than dropped like an unscoreable one."""
    const = np.full(SHAPE, 0.5)
    metrics, _ = qe.score_arrays(const, truth.astype(float), full_mask.astype(np.uint8), "chi")
    assert all(math.isfinite(v) for v in metrics.values()), metrics
    assert metrics["nrmse"] == pytest.approx(100.0, abs=1e-6)
    assert metrics["hfen"] == pytest.approx(100.0, abs=1e-6)
    assert metrics["correlation"] == 0.0


# ------------------------------------------------------ a constant truth: nothing to score against


@pytest.mark.parametrize("value", [0.5, -2.0, 0.0])
def test_a_constant_truth_scores_both_nrmse_variants_as_nan(recon, full_mask, value):
    """The mirror case: a flat TRUTH demeans to all zeros, so there is nothing to normalise by and
    the `norm_truth < 1e-30` guard returns NaN for both variants."""
    const_truth = np.full(SHAPE, value, dtype="float32")
    plain, detrended = qe.nrmse_challenge(recon, const_truth, full_mask)
    assert math.isnan(plain) and math.isnan(detrended)


@pytest.mark.parametrize("value", [0.5, -2.0, 0.0, 1e-9])
def test_a_constant_truth_scores_hfen_as_nan_for_every_constant(recon, full_mask, value):
    """Was a NaN-vs-huge-number split on the same degenerate input, and is now NaN throughout.

    HFEN used to guard on the LoG norm of the truth, which is EXACTLY zero only for an all-zero
    volume: for any other constant the truncated (5σ) LoG kernel's ~1e-5 non-zero sum leaves a floor
    that clears the 1e-30 guard, and the ratio came back finite and absurd (~4e7 % for 0.5, ~2e16 %
    for 1e-9 — note it scales with 1/truth, the signature of dividing by rounding noise rather than
    measuring anything). That was the same "nothing to score" case, not a numeric artefact to be
    tolerated: a constant truth has no fine detail at all, so the fraction of it recovered is
    undefined. HFEN now asks the same question NRMSE does — is the demeaned truth norm zero — so the
    two metrics agree on exactly which inputs are unscoreable."""
    const_truth = np.full(SHAPE, value, dtype="float32")
    assert math.isnan(qe.hfen(recon, const_truth, full_mask))


def test_a_merely_low_frequency_truth_is_still_scored(full_mask):
    """The guard is on a CONSTANT truth, not on a smooth one, and this pins that it is not wider than
    that. A linear ramp has no LoG in its interior (the Laplacian of an affine function is 0), but
    reflect padding bends it at the volume edge, so the truth really does carry high-frequency
    energy there and HFEN reports an ordinary percentage against it rather than NaN."""
    ramp = np.tile(np.linspace(-1.0, 1.0, SHAPE[0])[:, None, None], (1, SHAPE[1], SHAPE[2]))
    recon = np.random.default_rng(2).standard_normal(SHAPE)
    val = qe.hfen(recon, ramp, full_mask)
    assert math.isfinite(val) and 0.0 < val < 1e3, val


@pytest.mark.parametrize("value", [0.5, -2.0, 0.0])
def test_a_constant_truth_has_zero_correlation(recon, full_mask, value):
    """Unchanged, and deliberately so: as with a constant recon, 0.0 here is the zero-VARIANCE
    answer under a valid mask, not the no-voxels one."""
    const_truth = np.full(SHAPE, value, dtype="float32")
    assert qe.correlation(recon, const_truth, full_mask) == 0.0
