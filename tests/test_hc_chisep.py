"""HC-ChiSep: the two guards that stop it behaving like a different algorithm.

1. The protocol gate. The WM branch reads a multi-compartment signature out of the multi-echo
   magnitude, and the model-selection statistic cannot tell that signature from ordinary static
   dephasing when the echo train ends before the myelin pool has decayed. Measured on the
   chisep-mc phantom (the one with a genuine simulated beat) by decimating its echo train and
   scoring separability against single-compartment white matter: TE span 18 ms -> AUC 0.57,
   24 -> 0.58, 30 -> 0.63, 36 -> 0.72-0.77. The published chi-separation protocols that fall
   below the gate must therefore fall back to the closed form rather than guess.

2. The closed-form two-source solve must reduce to both published conventions exactly, so that
   Dr- is a real parameter rather than an inherited constant.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RECON = Path(__file__).resolve().parents[1] / "algorithms" / "hc-chisep-qsmci" / "recon.py"


@pytest.fixture(scope="module")
def hc():
    spec = importlib.util.spec_from_file_location("hc_chisep_recon", RECON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# (label, TEs in ms, expected admissible) — the real protocols of the scored phantoms.
PROTOCOLS = [
    ("chisep-mc  (8 echoes, 3-45 ms)", [3, 9, 15, 21, 27, 33, 39, 45], True),
    ("ridani-7t  (4 echoes, 4-28 ms)", [4, 12, 20, 28], False),
    ("ridani-3t  (6 echoes, 3-23 ms)", [3, 7, 11, 15, 19, 23], False),
]


@pytest.mark.parametrize("label,tes_ms,admissible", PROTOCOLS, ids=[p[0].split()[0] for p in PROTOCOLS])
def test_protocol_gate_matches_measured_detectability(hc, label, tes_ms, admissible):
    """Only an echo train that outlasts the myelin pool may run the WM branch."""
    ok, why = hc.protocol_supports_beat(np.asarray(tes_ms, float) / 1000.0)
    assert ok is admissible, f"{label}: gate said ok={ok} (reasons: {why})"
    assert bool(why) is not admissible, f"{label}: reasons must be given iff rejected"


def test_gate_rejects_a_short_train_however_many_echoes(hc):
    """Echo COUNT does not buy resolving power — span and TE_max do. A 32-echo train packed
    into 3-21 ms stays inadmissible; 4 echoes reaching 39 ms are admissible."""
    dense_but_short = np.linspace(3, 21, 32) / 1000.0
    sparse_but_long = np.asarray([3.0, 15.0, 27.0, 39.0]) / 1000.0
    assert hc.protocol_supports_beat(dense_but_short)[0] is False
    assert hc.protocol_supports_beat(sparse_but_long)[0] is True


def test_gate_thresholds_are_tied_to_the_myelin_t2(hc):
    """The gate must be derived from T2_myelin, not hard-coded milliseconds — otherwise it is a
    tuned constant rather than a physical criterion."""
    t2m = hc.WM_HC_PARAMS["T2_M"]
    just_under = np.asarray([0.0, hc.SPAN_MIN_T2M * t2m * 0.99]) + hc.TEMAX_MIN_T2M * t2m
    just_over = np.asarray([0.0, hc.SPAN_MIN_T2M * t2m * 1.01]) + hc.TEMAX_MIN_T2M * t2m
    assert hc.protocol_supports_beat(just_under)[0] is False
    assert hc.protocol_supports_beat(just_over)[0] is True


def _closed_form(rho, chi_total, dr_pos, dr_neg):
    """The solve as implemented in recon.py's non-WM branch."""
    return np.clip((rho + dr_neg * chi_total) / (dr_pos + dr_neg), 0, None)


def test_closed_form_reduces_to_the_ridani_convention():
    """Dr- = 0: all R2' is paramagnetic, chi+ = R2'/Dr+."""
    rho, chi_total, drp = np.array([10.0, 40.0, 90.0]), np.array([0.02, -0.03, 0.10]), 320.0
    assert np.allclose(_closed_form(rho, chi_total, drp, 0.0), rho / drp)


def test_closed_form_reduces_to_the_colocated_convention():
    """Dr- = Dr+: the symmetric Shin solve, chi+ = (R2'/D + chi_total)/2."""
    rho, chi_total, d = np.array([10.0, 40.0, 90.0]), np.array([0.02, -0.03, 0.10]), 320.0
    assert np.allclose(_closed_form(rho, chi_total, d, d), (rho / d + chi_total) / 2.0)


def test_closed_form_inverts_its_own_forward_model():
    """Round-trip: build R2' from a known (chi+, chi-) pair under some (Dr+, Dr-) and recover
    chi+ exactly. Catches a sign or normalisation slip in the generalised solve."""
    rng = np.random.default_rng(0)
    chi_pos = rng.uniform(0.0, 0.15, 500)
    chi_neg = rng.uniform(0.0, 0.06, 500)
    for drp, drn in [(320.0, 0.0), (320.0, 160.0), (755.0, 320.0), (137.0, 137.0)]:
        rho = drp * chi_pos + drn * chi_neg
        recovered = _closed_form(rho, chi_pos - chi_neg, drp, drn)
        assert np.allclose(recovered, chi_pos, atol=1e-12), f"failed at Dr+={drp}, Dr-={drn}"


def test_self_calibration_is_not_the_default(hc):
    """Dr+ must default to the published constant. The lower-envelope estimator recovers a
    noiseless phantom generator's Dr+ to four significant figures but spans 241-755 Hz/ppm once
    R2' is estimated, so it may only be reached by explicitly asking for it."""
    src = RECON.read_text()
    assert 'os.environ.get("HCCHISEP_DRP", "")' in src, "Dr+ must read a declared parameter"
    assert 'if drp_opt == "auto":' in src, "self-calibration must be opt-in via DRP=auto"
    i_default = src.index("dr_default = 137.0 * B0 / 3.0")
    i_auto = src.index('if drp_opt == "auto":')
    assert i_default < i_auto, "the published value must be the fallback, not the override"


def test_dr_neg_defaults_to_the_symmetric_convention(hc):
    """Dr- = Dr+ is the default because it survives an imperfect R2'.

    Measured on chisep-mc (avg MSPE): handed the TRUE R2', Dr-=0 scores 0.78 and Dr-=Dr+ 2.69;
    with a GENERATED R2' (corr 0.70, slope 0.41) Dr-=0 degrades 10.9x to 8.54 while Dr-=Dr+
    improves to 1.94. Dr- also fixes the weighting between the two input channels -- Dr-=0 reads
    chi+ off R2' alone -- so reverting this default silently restores that fragility."""
    src = RECON.read_text()
    assert 'os.environ.get("HCCHISEP_DRN", "drp")' in src, (
        "Dr- must default to drp (symmetric); Dr-=0 is only robust when R2' and Dr+ are exact"
    )
