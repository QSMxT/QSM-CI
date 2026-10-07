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


def test_runsfile_stamps_rows_with_the_ci_run_that_scored_them(pipeline, tmp_path, monkeypatch):
    monkeypatch.setenv("QSMCI_RUN", "123.2")
    monkeypatch.setenv("QSMCI_SHA", "abc")
    runs = pipeline.RunsFile(tmp_path / "runs-f-x.json")
    runs.append({"id": "a"})
    runs.extend([{"id": "b"}, {"id": "c", "ci_run": "7.1"}])   # an already-stamped row keeps its stamp
    assert [(r["ci_run"], r.get("ci_sha")) for r in runs] == [("123.2", "abc"), ("123.2", "abc"), ("7.1", None)]
    monkeypatch.delenv("QSMCI_RUN")
    runs.append({"id": "d"})
    assert "ci_run" not in runs[-1]                              # local runs are unstamped


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


def test_scoring_env_reports_the_modules_that_are_actually_loaded(pipeline):
    """`ci_env` must describe what RAN, not what eval/requirements.txt asked for: the interpreter
    and the numeric stack whose build moves the metric values (#211)."""
    import platform

    import nibabel
    import numpy
    import scipy

    env = pipeline.scoring_env()
    assert env["python"] == platform.python_version()
    assert (env["numpy"], env["scipy"], env["nibabel"]) == (numpy.__version__, scipy.__version__,
                                                            nibabel.__version__)
    assert set(env) <= {"python", "numpy", "scipy", "nibabel", "pillow"}   # compact, fixed key set
    assert all(isinstance(v, str) for v in env.values())                   # JSON-safe scalars only
    assert pipeline.scoring_env() is env                                   # resolved once per process


def test_runsfile_stamps_the_scoring_environment_onto_every_ci_row(pipeline, tmp_path, monkeypatch):
    """Stamped under the same condition as `ci_run`, per row (index.json merges rows from several
    runners, and merge_index.py rebuilds the document from main's index, so an index-level key
    could not survive a merge). An already-stamped row keeps the environment it was scored in."""
    monkeypatch.setenv("QSMCI_RUN", "900.1")
    monkeypatch.setenv("QSMCI_SHA", "deadbeef")
    out = tmp_path / "runs-f-env.json"
    runs = pipeline.RunsFile(out)
    runs.append({"id": "a"})
    runs.extend([{"id": "b", "ci_run": "7.1", "ci_env": {"python": "3.10.18"}}, {"id": "c"}])
    env = pipeline.scoring_env()
    assert runs[0]["ci_env"] == env and runs[2]["ci_env"] == env
    assert runs[0]["ci_env"] is not runs[2]["ci_env"]             # a copy per row, not one shared dict
    assert runs[1]["ci_env"] == {"python": "3.10.18"}             # the environment that scored it
    assert json.loads(out.read_text())[0]["ci_env"] == env        # persisted with the row
    monkeypatch.delenv("QSMCI_RUN")
    runs.append({"id": "d"})
    assert "ci_env" not in runs[-1] and "ci_run" not in runs[-1]  # local runs stay unstamped


def test_a_row_carrying_the_scoring_environment_round_trips_through_merge_index(pipeline):
    """merge_index upserts by id and diffs whole rows, so the new field must neither break the
    upsert nor go unnoticed: a rescore in a different environment IS a changed row."""
    mi = pipeline.merge_index
    e310 = {"python": "3.10.18", "numpy": "2.2.6"}
    e312 = {"python": "3.12.12", "numpy": "2.2.6"}
    def row(i, env, run="100.1"):
        return {"id": i, "metrics": {"nrmse": 1}, "ci_run": run, "ci_env": dict(env)}
    base, scored = [row("x", e310)], [row("x", e312)]
    merged, skipped = mi.merge(base, scored, base)
    assert skipped == [] and [r["id"] for r in merged] == ["x"]
    assert merged[0]["ci_env"] == e312                            # re-applied, environment carried
    # and the newer-run guard still reads `ci_run` with the extra key present
    assert mi.superseded(row("x", e310, "100.1"), row("x", e312, "200.1"))
    assert mi.upsert([row("x", e310)], [])[0]["ci_env"] == e310
