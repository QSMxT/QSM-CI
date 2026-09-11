"""scripts/score_state.py — results/scoring-state.json: what a run finished, what is still owed.

The invariant the planner relies on: every change not yet scored is either in scored_sha..main or
in the pending lists. So an unfinished task must always land in pending, and only the NEWEST run
may clear entries (an older run's completed task may have scored a stale commit).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("score_state", ROOT / "scripts" / "score_state.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

SHARDS = [{"id": f"s{i:02d}", "shard": f"{i}/2"} for i in range(2)]
FOCUS = [{"id": "f-tkd", "focus": "tkd"}, {"id": "iv-tkd", "focus": "tkd", "track": "invivo"},
         {"id": "f-big", "focus": "big"}]
ANCESTOR = lambda a, b: True      # noqa: E731 — "the recorded sha is an ancestor of mine" (normal case)
NOT_ANCESTOR = lambda a, b: False  # noqa: E731


def test_unfinished_tasks_become_pending_and_finished_ones_clear_it():
    cur = {"scored_sha": "old", "pending_full": False, "pending_slugs": ["big", "vsharp"]}
    new = ss.update(cur, "new", FOCUS, done={"f-tkd", "iv-tkd"}, ancestor=ANCESTOR, now="t")
    assert new["scored_sha"] == "new"
    assert new["pending_slugs"] == ["big", "vsharp"] and new["pending_full"] is False   # f-big not done
    new = ss.update(cur, "new", FOCUS, done={"f-tkd", "iv-tkd", "f-big"}, ancestor=ANCESTOR, now="t")
    assert new["pending_slugs"] == ["vsharp"]                     # big cleared; vsharp still owed
    assert new["last_run"] == {"sha": "new", "planned": 3, "done": 3}


def test_a_dead_shard_owes_a_full_rerun_and_a_complete_sweep_pays_it_off():
    cur = {"scored_sha": "old", "pending_full": False, "pending_slugs": ["tkd"]}
    new = ss.update(cur, "new", SHARDS + FOCUS, done={"s00", "f-tkd", "iv-tkd", "f-big"}, ancestor=ANCESTOR, now="t")
    assert new["pending_full"] is True                             # s01 never finished
    assert new["pending_slugs"] == []                              # tkd's own focus tasks did finish
    cur = {"scored_sha": "old", "pending_full": True, "pending_slugs": ["tkd", "hostedonly"]}
    new = ss.update(cur, "new", SHARDS + FOCUS, done={"s00", "s01", "f-tkd", "iv-tkd", "f-big"}, ancestor=ANCESTOR, now="t")
    assert new["pending_full"] is False
    assert new["pending_slugs"] == []                              # a full sweep also covered the hosted-tier slug
    # a focused run that finishes does NOT pay off pending_full
    cur = {"scored_sha": "old", "pending_full": True, "pending_slugs": []}
    new = ss.update(cur, "new", FOCUS, done={t["id"] for t in FOCUS}, ancestor=ANCESTOR, now="t")
    assert new["pending_full"] is True


def test_an_older_run_publishing_late_only_adds_never_clears():
    cur = {"scored_sha": "newer", "pending_full": False, "pending_slugs": ["tkd"]}
    new = ss.update(cur, "older", FOCUS, done={"f-tkd", "iv-tkd"}, ancestor=NOT_ANCESTOR, now="t")
    assert new["scored_sha"] == "newer"                            # never regresses
    assert new["pending_slugs"] == ["big", "tkd"]                  # tkd NOT cleared (scored at a stale commit)
    assert new["pending_full"] is False


def test_owed_manual_tasks_persist_until_a_current_run_finishes_them():
    cur = {"scored_sha": "old", "pending_manual": ["f-slow", "iv-slow"]}
    # a run that skipped more manual work adds it; scored_sha moving on does not clear it
    new = ss.update(cur, "new", FOCUS, done={t["id"] for t in FOCUS}, ancestor=ANCESTOR, now="t",
                    skipped_manual=["f-slow2"])
    assert new["pending_manual"] == ["f-slow", "f-slow2", "iv-slow"]
    # an include_manual run that finished f-slow clears just that
    manual = [{"id": "f-slow", "focus": "slow"}, {"id": "iv-slow", "focus": "slow", "track": "invivo"}]
    new = ss.update(new, "new2", manual, done={"f-slow"}, ancestor=ANCESTOR, now="t")
    assert new["pending_manual"] == ["f-slow2", "iv-slow"]
    assert new["pending_slugs"] == ["slow"]                        # iv-slow was planned and did not finish
    # …but a stale (older) run finishing it clears nothing
    new = ss.update(new, "older", manual, done={"iv-slow"}, ancestor=NOT_ANCESTOR, now="t")
    assert new["pending_manual"] == ["f-slow2", "iv-slow"]


def test_manual_include_recovery_is_never_carried():
    new = ss.update({}, "s", [{"id": "manual-include", "include": "a,b", "mode": "composed"}], done=set(),
                    ancestor=ANCESTOR, now="t")
    assert new["pending_slugs"] == [] and new["pending_full"] is False and new["scored_sha"] == "s"


def test_cli_reads_done_markers_from_the_merged_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    (tmp_path / "runs-f-tkd.json").write_text("[]")
    (tmp_path / "runs-f-tkd.done").write_text("0\n")
    (tmp_path / "runs-f-big.json").write_text("[]")               # rows flushed, but no marker → unfinished
    (tmp_path / "tasks.json").write_text(json.dumps(FOCUS))
    state = tmp_path / "results" / "scoring-state.json"
    r = subprocess.run(["python3", str(ROOT / "scripts" / "score_state.py"), "--state", str(state),
                        "--sha", "abc", "--tasks", "tasks.json"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    doc = json.loads(state.read_text())
    assert doc["scored_sha"] == "abc" and doc["pending_slugs"] == ["big", "tkd"]   # iv-tkd had no marker either
    assert "unfinished: iv-tkd, f-big" in r.stdout
