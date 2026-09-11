"""pipeline.py pieces that keep CI scoring from wasting work:

  - `compose:` — a dipole method too expensive for the full (field-map × bfr) matrix declares the
    columns it composes on; every enumeration (focus job, shard, upstream-DNF rows) honours it;
  - RunsFile — a --runs-out job persists every row as it lands and writes a `.done` marker only at
    the end, so a job killed at its cap hands merge what it finished AND merge can tell it did not
    finish (see scripts/score_state.py).
"""
from __future__ import annotations

import json

import pytest


def _algo(pipeline, slug, stage, compose=None):
    return {"slug": slug, "stage": stage, "name": slug, "image": "x", "compose": compose,
            "consumes": pipeline.STAGES[stage]["consumes"], "produces": pipeline.STAGES[stage]["produces"],
            "tuned": {}, "smoke_box": None, "smoke_params": {}}


def test_compose_spec_parsing_and_predicate(pipeline):
    assert pipeline._compose_spec({}, "m") is None
    c = pipeline._compose_spec({"compose": {"fieldmaps": ["gt", "romeo"], "bfrs": ["vsharp"]}}, "m")
    assert c == {"fieldmaps": {"gt", "romeo"}, "bfrs": {"vsharp"}}
    d = {"compose": c}
    assert pipeline.composes(d, "gt", "vsharp") and pipeline.composes(d, "romeo", "vsharp")
    assert not pipeline.composes(d, "gt", "pdf") and not pipeline.composes(d, "laplacian", "vsharp")
    only_bfr = {"compose": pipeline._compose_spec({"compose": {"bfrs": ["pdf"]}}, "m")}
    assert pipeline.composes(only_bfr, "anything", "pdf") and not pipeline.composes(only_bfr, "gt", "vsharp")
    assert pipeline.composes({"compose": None}, "gt", "pdf")
    for bad in ({"compose": []}, {"compose": {}}, {"compose": {"dipoles": ["x"]}}, {"compose": {"bfrs": []}},
                {"compose": {"bfrs": "vsharp"}}):
        with pytest.raises(SystemExit):
            pipeline._compose_spec(bad, "m")


def test_a_restricted_dipole_focus_job_only_computes_the_columns_it_needs(pipeline):
    fm = [_algo(pipeline, s, "field-mapping") for s in ("romeo", "laplacian")]
    bfr = [_algo(pipeline, s, "bfr") for s in ("vsharp", "pdf", "sharp")]
    heavy = _algo(pipeline, "heavy", "dipole", {"fieldmaps": {"gt"}, "bfrs": {"vsharp", "pdf"}})
    light = _algo(pipeline, "light", "dipole")
    plan = pipeline.plan_composed(fm + bfr + [heavy, light], "heavy", "sim", None, None)
    assert [b["slug"] for b in plan.bfr] == ["vsharp", "pdf"] and plan.fmap == []   # gt only, two bfrs
    assert plan.dipole == [heavy]
    plan = pipeline.plan_composed(fm + bfr + [heavy, light], "light", "sim", None, None)
    assert len(plan.bfr) == 3 and len(plan.fmap) == 2                             # unrestricted: everything


def test_runsfile_persists_every_row_and_marks_completion_only_at_the_end(pipeline, tmp_path):
    out = tmp_path / "shard" / "runs-f-x.json"
    runs = pipeline.RunsFile(out)
    assert json.loads(out.read_text()) == []                     # exists (empty) from the start
    runs.append({"id": "a"})
    assert json.loads(out.read_text()) == [{"id": "a"}]          # survives a kill right here
    runs.extend([{"id": "b"}, {"id": "c"}])
    assert [r["id"] for r in json.loads(out.read_text())] == ["a", "b", "c"]
    assert not out.with_suffix(".done").exists()                 # not finished → merge re-plans the task
    marker = runs.mark_done()
    assert marker == out.with_suffix(".done") and marker.read_text() == "3\n"
    assert not list(out.parent.glob("*.tmp"))                    # atomic replace leaves no temp file
    assert isinstance(runs, list) and len(runs) == 3            # still a plain list for the callers
