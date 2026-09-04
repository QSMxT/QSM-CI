"""The viewer's harmonization intermediates must be published once per unique map.

`pipeline.py --emit-intermediates` stages the field-mapping stage's total field and the
background-removal stage's local field for the submission page's Field map / Local field layers.
Those maps are per COLUMN, not per pipeline — one total field per field-mapping method, one local
field per (field-mapping, bfr) pair — so the whole point is that 660 pipelines produce 26 files, and
that splitting the matrix across shards (repro.yml runs `--shard i/N` per acquisition) doesn't turn
one file into N uploads of the same bytes.

A localfield is exactly-once by construction: its column belongs to one shard. A field map is not —
it is re-run in every shard that owns a column consuming it — which is what `tf_emit_owner` fixes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
pipeline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pipeline)

from qsm_ci.scoring import shard_owns  # noqa: E402 — the same round-robin run_composed uses

# The harmonization matrix's real shape: 2 field-mapping methods, 12 background-removal methods,
# and the bfr+dipole spans that compose with each field map.
FM = ["laplacian-qsmci", "romeo-qsmrs"]
BFR = ["bfrnet", "harperella-qsmrs", "iharperella-qsmrs", "iqfm", "ismv-qsmrs", "lbv-qsmrs",
       "msmv", "pdf-qsmrs", "resharp-qsmrs", "sharp-qsmrs", "vsharp-qsmrs", "vsharp-sti"]
SPANS = ["autoqsm", "nextqsm", "qsmart-qsmrs", "tfi-qsmrs", "tgv-qsmrs"]


def _columns(fm_keys, bfr_slugs, span_slugs):
    """The stable column ordering run_composed shards over: (source, bfr) pairs, then (source, span)."""
    col = {(t, b): i for i, (t, b) in enumerate((t, b) for t in fm_keys for b in bfr_slugs)}
    span = {(t, s): i for i, (t, s) in enumerate((t, s) for t in fm_keys for s in span_slugs)}
    return col, span


def _emitters(fm_keys, bfr_slugs, span_slugs, shard_i, shard_n):
    col, span = _columns(fm_keys, bfr_slugs, span_slugs)
    owns_col = lambda t, b: shard_owns(col.get((t, b), 0), shard_i, shard_n)      # noqa: E731
    owns_span = lambda t, s: shard_owns(span.get((t, s), 0), shard_i, shard_n)    # noqa: E731
    return pipeline.tf_emit_owner(col, span, owns_col, owns_span)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 12, 24, 64])
def test_each_field_map_is_published_by_exactly_one_shard(n):
    """Whatever the shard count, the n shards together publish each field map once — no gaps (a map
    the viewer would 404 on) and no duplicates (the same bytes uploaded n times)."""
    emitted = [tfk for i in range(n) for tfk in _emitters(FM, BFR, SPANS, i, n)]
    assert sorted(emitted) == sorted(FM), f"{n} shards published {sorted(emitted)}"


def test_sharding_off_publishes_every_field_map():
    assert _emitters(FM, BFR, SPANS, None, None) == set(FM)


def test_a_source_reached_only_through_spans_is_still_published():
    """A field map with no bfr columns (every dipole method is a bfr+dipole span) is still consumed —
    by the span columns — so it must still be published, not dropped for lack of a bfr column."""
    emitted = [tfk for i in range(4) for tfk in _emitters(FM, [], SPANS, i, 4)]
    assert sorted(emitted) == sorted(FM)


def test_a_source_nothing_consumes_is_not_published():
    """No columns at all means no pipeline uses that field map, so there is nothing to show."""
    assert _emitters(FM, [], [], None, None) == set()


def test_localfield_columns_partition_across_shards():
    """The companion property this rule leans on: every (field-mapping, bfr) column is owned by
    exactly one shard, so a localfield is written once without any extra bookkeeping."""
    col, _ = _columns(FM, BFR, SPANS)
    for n in (1, 3, 6, 7):
        owned = [k for i in range(n) for k in col if shard_owns(col[k], i, n)]
        assert sorted(owned) == sorted(col), f"{n} shards did not partition the bfr columns"


def test_emitted_names_match_the_urls_the_viewer_derives():
    """viewer.js builds `<fm>__totalfield.nii.gz` and `<fm>_<bfr>__localfield.nii.gz` from the
    pipeline id; pipeline.py must stage exactly those basenames or the layers silently never appear."""
    src = (ROOT / "web" / "js" / "viewer.js").read_text()
    assert "${fm}__totalfield.nii.gz" in src
    assert "${fm}_${bfr}__localfield.nii.gz" in src
    pipe_src = (ROOT / "scripts" / "pipeline.py").read_text()
    assert '__totalfield", res[1])' in pipe_src
    assert '__localfield", res[1][0])' in pipe_src


def test_focus_run_republishes_every_field_map_it_built():
    """A --focus run isn't sharded, so it is the canonical publisher of every field map it built.
    Focusing a bfr changes none of them, so these are identical-byte re-publishes (deduplicated
    Hub-side) that keep the set self-healing. The waste that actually matters — rebuilding the
    upstream just to feed a changed DIPOLE method — is cut off in repro.yml's plan job instead."""
    assert _emitters(FM, ["vsharp-qsmrs"], [], None, None) == set(FM)


def test_focus_on_a_field_mapping_publishes_that_field_map():
    """Focusing a field-mapping method rebuilds its total field, so it must be re-published."""
    assert _emitters(["romeo-qsmrs"], BFR, [], None, None) == {"romeo-qsmrs"}
