"""The viewer's harmonization intermediates must be published once per unique map.

`pipeline.py --emit-intermediates` stages the field-mapping stage's total field and the
background-removal stage's local field for the submission page's Field map / Local field layers.
Those maps are per COLUMN, not per pipeline — one total field per field-mapping method, one local
field per (field-mapping, bfr) pair — so the whole point is that 660 pipelines produce 26 files, and
that splitting the matrix across shards (repro.yml runs `--shard i/N` per acquisition) doesn't turn
one file into N uploads of the same bytes.

A localfield is exactly-once by construction: its column belongs to one shard. A field map is not —
it is re-run in every shard that owns a column consuming it — which is what `tf_emit_owner` fixes.

The column ordering and ownership come from the REAL `plan_composed` (the pure half of
run_composed), fed discover_algorithms()-shaped rows — not a copy of its arithmetic kept here — so
if the ordering ever drifts, these tests see the drift.
"""

from __future__ import annotations

import pytest

# The harmonization matrix's real shape: 2 field-mapping methods, 12 background-removal methods,
# and the bfr+dipole spans that compose with each field map.
FM = ["laplacian-qsmci", "romeo-qsmrs"]
BFR = ["bfrnet", "harperella-qsmrs", "iharperella-qsmrs", "iqfm", "ismv-qsmrs", "lbv-qsmrs",
       "msmv", "pdf-qsmrs", "resharp-qsmrs", "sharp-qsmrs", "vsharp-qsmrs", "vsharp-sti"]
SPANS = ["autoqsm", "nextqsm", "qsmart-qsmrs", "tfi-qsmrs", "tgv-qsmrs"]
TRACK = "repro"  # harmonization: a no-ground-truth track, so no "gt" total-field source


def _algos(pipeline, fm_slugs, bfr_slugs, span_slugs) -> list:
    """discover_algorithms()-shaped rows (the fields plan_composed reads), with each stage's
    consumes/produces taken from the same STAGES table discovery fills them from."""
    def row(slug, stage):
        return {"slug": slug, "stage": stage, "name": slug,
                "consumes": pipeline.STAGES[stage]["consumes"],
                "produces": pipeline.STAGES[stage]["produces"]}
    return ([row(s, "field-mapping") for s in fm_slugs] + [row(s, "bfr") for s in bfr_slugs]
            + [row(s, "bfr+dipole") for s in span_slugs])


def _plan(pipeline, fm, bfr, spans, shard_i, shard_n, focus=None):
    return pipeline.plan_composed(_algos(pipeline, fm, bfr, spans), focus, TRACK, shard_i, shard_n)


def _emitters(pipeline, fm, bfr, spans, shard_i, shard_n, focus=None) -> set:
    p = _plan(pipeline, fm, bfr, spans, shard_i, shard_n, focus)
    return pipeline.tf_emit_owner(p.col_owner, p.span_owner, p.owns_col, p.owns_span)


def test_columns_are_source_major_in_slug_order(pipeline):
    """The stable ordering every shard must agree on: (source, bfr) pairs source-major with bfrs in
    slug order, then (source, span) pairs the same way — independent of discovery order, and with
    the ground-truth field first on a track that has one."""
    shuffled = list(reversed(BFR))
    p = _plan(pipeline, list(reversed(FM)), shuffled, list(reversed(SPANS)), None, None)
    assert list(p.col_owner) == [(t, b) for t in FM for b in BFR]
    assert list(p.col_owner.values()) == list(range(len(FM) * len(BFR)))
    assert list(p.span_owner) == [(t, s) for t in FM for s in SPANS]
    assert p.fm_keys == FM and p.no_gt
    sim = pipeline.plan_composed(_algos(pipeline, FM, BFR, SPANS), None, "sim", None, None)
    assert sim.fm_keys == ["gt"] + FM and not sim.no_gt
    assert list(sim.col_owner)[:len(BFR)] == [("gt", b) for b in BFR]


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 12, 24, 64])
def test_each_field_map_is_published_by_exactly_one_shard(pipeline, n):
    """Whatever the shard count, the n shards together publish each field map once — no gaps (a map
    the viewer would 404 on) and no duplicates (the same bytes uploaded n times)."""
    emitted = [tfk for i in range(n) for tfk in _emitters(pipeline, FM, BFR, SPANS, i, n)]
    assert sorted(emitted) == sorted(FM), f"{n} shards published {sorted(emitted)}"


def test_sharding_off_publishes_every_field_map(pipeline):
    assert _emitters(pipeline, FM, BFR, SPANS, None, None) == set(FM)


def test_a_source_reached_only_through_spans_is_still_published(pipeline):
    """A field map with no bfr columns (every dipole method is a bfr+dipole span) is still consumed —
    by the span columns — so it must still be published, not dropped for lack of a bfr column."""
    emitted = [tfk for i in range(4) for tfk in _emitters(pipeline, FM, [], SPANS, i, 4)]
    assert sorted(emitted) == sorted(FM)


def test_a_source_nothing_consumes_is_not_published(pipeline):
    """No columns at all means no pipeline uses that field map, so there is nothing to show."""
    assert _emitters(pipeline, FM, [], [], None, None) == set()


def test_localfield_columns_partition_across_shards(pipeline):
    """The companion property this rule leans on: every (field-mapping, bfr) column is owned by
    exactly one shard, so a localfield is written once without any extra bookkeeping."""
    every = list(_plan(pipeline, FM, BFR, SPANS, None, None).col_owner)
    for n in (1, 3, 6, 7):
        owned = [k for i in range(n) for k in every
                 if _plan(pipeline, FM, BFR, SPANS, i, n).owns_col(*k)]
        assert sorted(owned) == sorted(every), f"{n} shards did not partition the bfr columns"


def test_a_shard_only_runs_the_field_maps_its_columns_consume(pipeline):
    """plan_composed prunes `fmap` to the sources this shard actually needs: with 2 field maps × 12
    bfr columns split 24 ways, each shard owns one column and so runs exactly one field map."""
    for i in range(24):
        p = _plan(pipeline, FM, BFR, [], i, 24)
        assert [f["slug"] for f in p.fmap] == [next(t for (t, b) in p.col_owner if p.owns_col(t, b))]


def test_emitted_names_match_the_urls_the_viewer_derives(pipeline):
    """viewer.js builds `<fm>__totalfield.nii.gz` and `<fm>_<bfr>__localfield.nii.gz` from the
    pipeline id; pipeline.py must stage exactly those basenames or the layers silently never appear."""
    src = (pipeline.ROOT / "web" / "js" / "viewer.js").read_text()
    assert "${fm}__totalfield.nii.gz" in src
    assert "${fm}_${bfr}__localfield.nii.gz" in src
    pipe_src = (pipeline.ROOT / "scripts" / "pipeline.py").read_text()
    assert '__totalfield", res[1])' in pipe_src
    assert '__localfield", res[1][0])' in pipe_src


def test_focus_run_republishes_every_field_map_it_built(pipeline):
    """A --focus run isn't sharded, so it is the canonical publisher of every field map it built.
    Focusing a bfr changes none of them, so these are identical-byte re-publishes (deduplicated
    Hub-side) that keep the set self-healing. The waste that actually matters — rebuilding the
    upstream just to feed a changed DIPOLE method — is cut off in repro.yml's plan job instead."""
    p = _plan(pipeline, FM, BFR, SPANS, None, None, focus="vsharp-qsmrs")
    assert [b["slug"] for b in p.bfr] == ["vsharp-qsmrs"] and p.tf_spans == []  # pinned to the focus
    assert _emitters(pipeline, FM, BFR, SPANS, None, None, focus="vsharp-qsmrs") == set(FM)


def test_focus_on_a_field_mapping_publishes_that_field_map(pipeline):
    """Focusing a field-mapping method rebuilds its total field, so it must be re-published."""
    p = _plan(pipeline, FM, BFR, SPANS, None, None, focus="romeo-qsmrs")
    assert [f["slug"] for f in p.fmap] == ["romeo-qsmrs"]
    assert _emitters(pipeline, FM, BFR, SPANS, None, None, focus="romeo-qsmrs") == {"romeo-qsmrs"}
