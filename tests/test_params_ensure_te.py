"""qsm_ci/params.py — who gets a placeholder echo time, and who must be told to supply one.

BFR and dipole-inversion stages work on a field that is already in ppm: TE never enters the physics,
and the TE*B0 scaling some recon code applies cancels out. That code still indexes TE(1) though, so
writing `TE: []` hands the container an empty array it indexes anyway ("Index exceeds array bounds").
`_ensure_te` fills in a nominal TE=[1.0] for exactly those stages — and refuses to invent one for a
phase-consuming stage, where a fabricated echo time would silently change the result instead of
failing. Both halves of that rule are load-bearing, so they are pinned per stage off the contract in
STAGES rather than against a hand-written list that could drift from it.
"""
from __future__ import annotations

import pytest

from qsm_ci.params import _ensure_te
from qsm_ci.stages import STAGES

PHASE_STAGES = [s for s, spec in STAGES.items() if "phase" in spec["consumes"]]
PPM_STAGES = [s for s, spec in STAGES.items() if "phase" not in spec["consumes"]]


def test_the_contract_has_stages_on_both_sides_of_the_rule():
    """Guard the parametrisation itself: if either list went empty the tests below would pass by
    vacuously testing nothing."""
    assert PHASE_STAGES and PPM_STAGES


@pytest.mark.parametrize("stage", PPM_STAGES)
def test_a_ppm_stage_gets_a_nominal_placeholder_when_te_is_omitted(stage):
    assert _ensure_te([], stage) == [1.0]


@pytest.mark.parametrize("stage", PHASE_STAGES)
def test_a_phase_consuming_stage_never_has_an_echo_time_invented_for_it(stage):
    """The empty list is passed straight back so the caller can raise a "pass --te" error; silently
    scaling by a made-up TE would corrupt the field map instead."""
    assert _ensure_te([], stage) == []


@pytest.mark.parametrize("stage", list(STAGES))
@pytest.mark.parametrize("te", [[0.02], [0.004, 0.012, 0.02], [0.0]])
def test_a_supplied_echo_time_is_returned_untouched_for_every_stage(stage, te):
    """Including TE=[0.0], which is falsey per element but a non-empty list — the guard tests the
    LIST, so a zero echo time must survive rather than be replaced by the placeholder."""
    assert _ensure_te(list(te), stage) == te


@pytest.mark.parametrize("stage", list(STAGES))
def test_the_caller_s_list_is_not_mutated(stage):
    te: list = []
    out = _ensure_te(te, stage)
    assert te == []              # the placeholder is a new list, not an append to the caller's
    assert out in ([], [1.0])


def test_an_unknown_stage_is_a_keyerror_not_a_silent_placeholder():
    """`_ensure_te` consults STAGES[stage]["consumes"]; a typo'd stage must blow up loudly rather
    than fall through to the TE=[1.0] branch and run phase data through a nominal echo time."""
    with pytest.raises(KeyError):
        _ensure_te([], "not-a-stage")
