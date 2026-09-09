"""`prune_stale_tuned.py` drops rows from index.json, so a false positive silently deletes a run.

It used to reimplement the tuned-value lookup instead of calling pipeline._tuned_overrides, and the
copy had drifted: it keyed on TRACK only, while `tuned:` may also be keyed by a specific PHANTOM.
Every per-phantom tuned run therefore compared against a declaration that did not exist — on the
2026-09 index, 4 of 4 tuned r2prime-scaled-qsmci runs, all of which match their phantom exactly.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import prune_stale_tuned as pst  # noqa: E402


def _run(**kw):
    base = dict(id="r", slug="r2prime-scaled-qsmci", mode="isolated", variant="tuned", track="sim")
    base.update(kw)
    return base


@pytest.mark.parametrize("phantom,fraction", [
    ("ridani-3t-iso", "0.8"), ("ridani-3t-aniso", "0.9"), ("ridani-7t-aniso", "0.9"),
])
def test_phantom_keyed_tuning_is_not_stale(phantom, fraction):
    """The regression: these matched their declared value and were all reported stale."""
    assert not pst.is_stale(_run(phantom=phantom, params={"fraction": fraction}))


def test_chisep_row_stamped_track_sim_resolves_via_domain():
    """chi-sep rows carry `track: sim` with `domain: chisep`; keying on track finds nothing."""
    run = _run(phantom="chisep-mc", domain="chisep", params={"fraction": "0.6"})
    assert not pst.is_stale(run)


def test_a_value_that_does_not_match_the_declaration_is_stale():
    assert pst.is_stale(_run(phantom="ridani-3t-iso", params={"fraction": "0.123"}))


def test_unknown_method_is_kept_not_deleted():
    """A missing algorithm.yml means this checkout cannot answer, not that tuning was withdrawn."""
    assert pst.declared_tuned("no-such-method", "sim", None) is None
    assert not pst.is_stale(_run(slug="no-such-method", params={"fraction": "0.9"}))


def test_declared_tuned_distinguishes_cannot_tell_from_nothing_declared():
    assert pst.declared_tuned("no-such-method", "sim", None) is None       # cannot tell
    assert pst.declared_tuned("r2prime-scaled-qsmci", "sim", None) == {}   # nothing for this key


def test_non_tuned_rows_are_never_touched():
    assert not pst.is_stale(_run(variant="default", params={"fraction": "0.9"}))
    assert not pst.is_stale(_run(mode="composed", params={"fraction": "0.9"}))


def test_the_committed_index_has_no_stale_runs():
    """Guards the whole pipeline end to end: a regression here deletes real published rows."""
    doc = json.loads((ROOT / "results" / "index.json").read_text())
    stale = [r["id"] for r in doc["runs"] if pst.is_stale(r)]
    assert stale == []
