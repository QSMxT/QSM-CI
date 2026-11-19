"""A stage the scorer cannot score is not run by the scoring sweep (pipeline.run_isolated).

brain-extraction's output IS the mask and there is no metric set for one (qsm_ci.stages.scorable), so
its four submissions only ever produced `'mask'` DNF rows (score run 44225121850). The smoke gate
still runs them, to check the submission works.
"""
from __future__ import annotations

from types import SimpleNamespace


def _ran(pipeline, monkeypatch, smoke):
    seen = []
    monkeypatch.setattr(pipeline, "do_isolated", lambda task, *a: seen.append(task[0]["slug"]) or [])
    args = SimpleNamespace(smoke=smoke, shard=None, runs_out="x.json", inputs="gt")
    algos = [{"slug": "be", "stage": "brain-extraction"}, {"slug": "dp", "stage": "dipole"}]
    pipeline.run_isolated(args, algos, {}, None, None, None, [])
    return sorted(seen)


def test_brain_extraction_is_not_scored(pipeline, monkeypatch):
    assert _ran(pipeline, monkeypatch, smoke=False) == ["dp"]


def test_brain_extraction_still_smoke_tested(pipeline, monkeypatch):
    assert _ran(pipeline, monkeypatch, smoke=True) == ["be", "dp"]
