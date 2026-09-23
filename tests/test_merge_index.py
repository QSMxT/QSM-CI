"""scripts/merge_index.py — a rescore re-applies only the rows it changed, and never an OLDER run's
row over a NEWER run's (score runs overlap and merge in either order)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("merge_index", ROOT / "scripts" / "merge_index.py")
mi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mi)


def row(i, v, run=None):
    r = {"id": i, "metrics": {"nrmse": v}}
    if run:
        r["ci_run"] = run
    return r


def test_only_changed_rows_are_reapplied_and_order_is_kept():
    base = [row("a", 1), row("b", 1)]
    scored = [row("a", 1), row("b", 2), row("c", 3)]          # b changed, c new, a untouched
    current = [row("b", 9), row("a", 7), row("d", 4)]          # main moved on: a=7 and d landed elsewhere
    merged, skipped = mi.merge(base, scored, current)
    assert [r["id"] for r in merged] == ["b", "a", "d", "c"]
    assert merged[0]["metrics"]["nrmse"] == 2 and merged[1]["metrics"]["nrmse"] == 7 and skipped == []


def test_an_older_run_never_overwrites_a_newer_runs_row():
    assert mi.run_key({"ci_run": "34471062758.1"}) == (34471062758, 1)
    assert mi.run_key({}) == (0, 0) and mi.run_key({"ci_run": "junk"}) == (0, 0)
    newer, older = "200.1", "100.1"
    assert mi.superseded(row("x", 1, older), row("x", 2, newer))
    assert not mi.superseded(row("x", 1, newer), row("x", 2, older))
    assert not mi.superseded(row("x", 1, older), None)             # nothing on main yet
    assert not mi.superseded(row("x", 1, older), row("x", 2))      # unstamped (legacy) row on main
    assert mi.superseded(row("x", 1, "100.1"), row("x", 2, "100.2"))   # a re-run attempt is newer
    base = [row("x", 1, older), row("y", 1, older)]
    scored = [row("x", 5, older), row("y", 5, older)]              # the older run's late merge
    current = [row("x", 9, newer), row("y", 1, older)]            # a newer run already published x
    merged, skipped = mi.merge(base, scored, current)
    assert skipped == ["x"]
    assert {r["id"]: r["metrics"]["nrmse"] for r in merged} == {"x": 9, "y": 5}


def test_cli_writes_the_superseded_ids(tmp_path):
    for name, runs in (("base", [row("x", 1, "1.1")]), ("scored", [row("x", 2, "1.1"), row("z", 1, "1.1")]),
                       ("current", [row("x", 3, "2.1")])):
        (tmp_path / f"{name}.json").write_text(json.dumps({"runs": runs}))
    r = subprocess.run(["python3", str(ROOT / "scripts" / "merge_index.py"), *(str(tmp_path / f"{n}.json") for n in
                        ("base", "scored", "current", "out")), "--superseded-out", str(tmp_path / "sup.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "sup.json").read_text()) == ["x"]
    out = json.loads((tmp_path / "out.json").read_text())["runs"]
    assert {q["id"]: q["metrics"]["nrmse"] for q in out} == {"x": 3, "z": 1}
    assert "re-applied 1 changed run(s)" in r.stdout and "NOT applied" in r.stdout


def test_an_unreadable_scored_index_fails_loudly(tmp_path):
    """A corrupt SCORED used to read as "no runs": `changed` empty, "re-applied 0 changed run(s)",
    exit 0, nothing published. A whole rescore lost while the job stayed green."""
    (tmp_path / "base.json").write_text(json.dumps({"runs": [row("a", 1)]}))
    (tmp_path / "scored.json").write_text("{truncated")
    (tmp_path / "current.json").write_text(json.dumps({"runs": [row("a", 1)]}))
    r = subprocess.run(["python3", str(ROOT / "scripts" / "merge_index.py"),
                        *(str(tmp_path / f"{n}.json") for n in ("base", "scored", "current", "out"))],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "refusing to publish" in r.stderr
    assert not (tmp_path / "out.json").exists()


def test_a_missing_base_is_fine_but_a_missing_scored_is_not(tmp_path):
    """BASE may legitimately be absent (a first rescore); SCORED may not."""
    assert mi._runs(str(tmp_path / "nope.json"), required=False) == []
    try:
        mi._runs(str(tmp_path / "nope.json"))
    except SystemExit as e:
        assert "cannot read" in str(e)
    else:
        raise AssertionError("a missing SCORED must not read as 'no runs'")


def test_upsert_replaces_in_place_and_appends_new_ids():
    """The one merge policy — shared with pipeline.flush_index, which used to filter-then-append
    and so reordered results/index.json on every rescore."""
    existing = [row("a", 1), row("b", 1), row("c", 1)]
    merged = mi.upsert(existing, [row("b", 2), row("z", 9)])
    assert [r["id"] for r in merged] == ["a", "b", "c", "z"]
    assert merged[1]["metrics"]["nrmse"] == 2
    assert mi.upsert([], [row("a", 1)]) == [row("a", 1)]
    assert mi.upsert(existing, []) == existing
