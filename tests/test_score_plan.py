"""scripts/score_plan.py — the score.yml planner: what gets scored, where, and what is NOT lost.

The failure modes this pins down were all observed in the run history (2026-07 → 2026-09):
  - a push displaced from the concurrency queue was never scored (its scope vanished);
  - modip / inr-qsm were auto-scheduled on every full rescore, held a self-hosted runner for the
    whole cap and never finished (29 attempts, 1 success);
  - a docs-only algorithm.yml edit rescored the method's whole matrix;
  - a burst of pushes restarted a task that an in-flight run was already scoring correctly.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("score_plan", ROOT / "scripts" / "score_plan.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

REG = {"sim": {"track": "sim", "active": True, "default": True},
       "invivo": {"track": "invivo", "active": True, "default": True},
       "chisep-mc": {"track": "chisep", "active": True, "default": True},
       "ridani-3t-iso": {"track": "chisep", "active": True, "default": False},
       "ridani-7t-aniso": {"track": "chisep", "active": True, "default": False}}


def _algos(tmp_path: Path, specs: dict[str, str]) -> Path:
    root = tmp_path / "algorithms"
    for slug, body in specs.items():
        (root / slug).mkdir(parents=True)
        (root / slug / "algorithm.yml").write_text(body)
    return root


BASIC = {
    "tkd": "stage: dipole\nimage: x\n",
    "vsharp": "stage: bfr\nimage: x\n",
    "big": "stage: dipole\nimage: x\nrunner: self-hosted\ntimeout_minutes: 900\njobs: 1\n",
    "slow": "stage: dipole\nimage: x\nrunner: manual\ntimeout_minutes: 2880\njobs: 1\n",
    "gpuonly": "stage: dipole\nimage: x\nrunner: gpu\n",
    "chi": "stage: chi-separation\nimage: x\nrunner: self-hosted\nmanual_phantoms: [ridani-3t-iso]\n",
    "skipme": "stage: dipole\nimage: x\nci_skip: true\n",
}


# ---------------------------------------------------------------------------------------------- tiers

def test_manual_and_gpu_tiers_are_never_planned_automatically(tmp_path):
    root = _algos(tmp_path, BASIC)
    full = sp.plan_tasks(root, REG, full=True, slugs=[])
    ids = {t["id"] for t in full}
    assert "f-big" in ids and "iv-big" in ids                     # self-hosted: still automatic
    assert not {"f-slow", "iv-slow", "f-gpuonly", "iv-gpuonly"} & ids
    assert "f-chi" in ids and "f-chi-ridani-7t-aniso" in ids     # chisep phantoms: automatic …
    assert "f-chi-ridani-3t-iso" not in ids                       # … except the manual one
    focused = sp.plan_tasks(root, REG, full=False, slugs=["slow", "tkd"])
    assert {t["id"] for t in focused} == {"f-tkd", "iv-tkd"}      # a push touching `slow` plans nothing for it


def test_naming_a_manual_method_on_dispatch_plans_it(tmp_path):
    root = _algos(tmp_path, BASIC)
    t = {x["id"]: x for x in sp.plan_tasks(root, REG, full=False, slugs=["slow", "chi"], explicit={"slow", "chi"})}
    assert {"f-slow", "iv-slow", "f-chi", "f-chi-ridani-3t-iso", "f-chi-ridani-7t-aniso"} <= set(t)
    assert t["f-slow"]["runs_on"] == ["self-hosted", "Linux", "X64"]
    assert t["f-slow"]["timeout"] == 2880 and t["f-slow"]["jobs"] == 1
    everything = sp.plan_tasks(root, REG, full=True, slugs=[], include_manual=True)
    assert {"f-slow", "iv-slow", "f-gpuonly", "f-chi-ridani-3t-iso"} <= {x["id"] for x in everything}


def test_overrides_only_apply_on_self_hosted_tiers_and_skipped_methods_never_run(tmp_path):
    root = _algos(tmp_path, {
        "hosted-with-override": "stage: dipole\nimage: x\ntimeout_minutes: 900\njobs: 9\n", **BASIC})
    t = {x["id"]: x for x in sp.plan_tasks(root, REG, full=True, slugs=[], include_manual=True)}
    assert t["f-big"]["timeout"] == 900 and t["f-big"]["jobs"] == 1
    assert "f-hosted-with-override" not in t                       # hosted default → scored in the shards
    assert t["s00"]["timeout"] == 360 and t["s00"]["jobs"] == 2
    assert "skipme" not in {x.get("focus") for x in t.values()}
    # heavy dedicated dipoles are excluded from a bfr focus job and from the shards
    bfr = sp.plan_tasks(root, REG, full=False, slugs=["vsharp"])
    assert set(bfr[0]["exclude"].split(",")) == {"big", "slow", "gpuonly"}
    assert set(t["s00"]["exclude"].split(",")) >= {"big", "slow", "gpuonly", "chi"}


# ---------------------------------------------------------------------------------------------- scope

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tiny git repo laid out like QSM-CI (algorithms/, eval/), returning a commit helper."""
    subprocess.run(["git", "init", "-q", "-b", "main", tmp_path], check=True)
    monkeypatch.chdir(tmp_path)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "config", k, v], check=True)
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "m.py").write_text("1\n")
    root = _algos(tmp_path, {"tkd": "name: TKD\nstage: dipole\nimage: x\nparameters: [{name: thr, default: 0.19}]\n",
                             "vsharp": "stage: bfr\nimage: x\n"})

    def commit(msg: str, **files: str) -> str:
        for rel, body in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    base = commit("init")
    return {"root": root, "commit": commit, "base": base, "path": tmp_path}


def test_scope_accumulates_every_change_since_the_last_completed_scoring(repo):
    """Two pushes, then a plan: BOTH pushes' methods are in scope — not just the last one (the old
    'diff against the previous head' lost the earlier push whenever its run was displaced)."""
    c = repo["commit"]
    c("change tkd", **{"algorithms/tkd/run.sh": "echo 1\n"})
    head = c("change vsharp", **{"algorithms/vsharp/run.sh": "echo 2\n"})
    files = sp.changed_files(repo["base"], head)
    full, slugs = sp.scope_from_files(repo["root"], files, repo["base"], head)
    assert (full, slugs) == (False, ["tkd", "vsharp"])


def test_skip_score_is_honoured_per_commit_and_scorer_changes_go_full(repo):
    c = repo["commit"]
    c("docstring only [skip score]", **{"algorithms/tkd/run.sh": "echo 1\n"})
    head = c("real change", **{"algorithms/vsharp/run.sh": "echo 2\n"})
    full, slugs = sp.scope_from_files(repo["root"], sp.changed_files(repo["base"], head), repo["base"], head)
    assert (full, slugs) == (False, ["vsharp"])                    # tkd's skip-score commit contributed nothing
    head2 = c("scorer change", **{"eval/m.py": "2\n"})
    full, _ = sp.scope_from_files(repo["root"], sp.changed_files(repo["base"], head2), repo["base"], head2)
    assert full


def test_cosmetic_algorithm_yml_edits_do_not_rescore_but_matrix_changes_do(repo):
    c = repo["commit"]
    spec = (repo["root"] / "tkd" / "algorithm.yml").read_text()
    h1 = c("docs", **{"algorithms/tkd/algorithm.yml": spec + "description: nicer words\nrunner: hosted-large\n"})
    assert sp.scope_from_files(repo["root"], sp.changed_files(repo["base"], h1), repo["base"], h1) == (False, [])
    h2 = c("param", **{"algorithms/tkd/algorithm.yml": spec.replace("0.19", "0.25")})
    assert sp.scope_from_files(repo["root"], sp.changed_files(h1, h2), h1, h2) == (False, ["tkd"])
    h3 = c("compose", **{"algorithms/tkd/algorithm.yml": spec + "compose: {bfrs: [vsharp]}\n"})
    assert sp.scope_from_files(repo["root"], sp.changed_files(h2, h3), h2, h3) == (False, ["tkd"])
    h4 = c("new method", **{"algorithms/newone/algorithm.yml": "stage: dipole\nimage: x\n"})
    assert sp.scope_from_files(repo["root"], sp.changed_files(h3, h4), h3, h4) == (False, ["newone"])


def test_decide_carries_pending_work_and_falls_back_without_state(repo, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    c = repo["commit"]
    head = c("change vsharp", **{"algorithms/vsharp/run.sh": "echo 2\n"})
    env = {"EVENT": "push", "SHA": head, "BEFORE": repo["base"]}
    d = sp.decide(env, repo["root"], REG, {})                    # no state yet → BEFORE is the base
    assert d["base"] == repo["base"] and d["slugs"] == ["vsharp"] and not d["full"]
    assert [t["id"] for t in d["tasks"]] == ["f-vsharp"]
    state = {"scored_sha": repo["base"], "pending_full": False, "pending_slugs": ["tkd"]}
    d = sp.decide(env, repo["root"], REG, state)                 # an earlier run left tkd unfinished
    assert d["slugs"] == ["tkd", "vsharp"]
    assert {t["id"] for t in d["tasks"]} == {"f-tkd", "iv-tkd", "f-vsharp"}
    d = sp.decide(env, repo["root"], REG, {"scored_sha": repo["base"], "pending_full": True})
    assert d["full"] and any("shard" in t for t in d["tasks"])
    d = sp.decide(env, repo["root"], REG, {"scored_sha": "0" * 40})  # rewritten history → fallback
    assert d["base"] == repo["base"] and d["slugs"] == ["vsharp"]
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": head, "SCOPE": "tkd"}, repo["root"], REG, state)
    assert {t["id"] for t in d["tasks"]} == {"f-tkd", "iv-tkd"}  # explicit dispatch ignores pending


def test_manual_work_is_remembered_and_include_manual_runs_only_what_is_owed(repo, monkeypatch):
    """A push changes a manual-tier method: nothing is scheduled for it, but the planner reports
    the owed tasks (merge records them as pending_manual). Later, scope=auto + include_manual=true
    plans exactly those — not every manual method, and not nothing because scored_sha moved on."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    c = repo["commit"]
    (repo["root"] / "slow").mkdir()
    (repo["root"] / "slow" / "algorithm.yml").write_text("stage: dipole\nimage: x\nrunner: manual\n")
    (repo["root"] / "slow2").mkdir()
    (repo["root"] / "slow2" / "algorithm.yml").write_text("stage: dipole\nimage: x\nrunner: manual\n")
    head = c("add two manual methods")
    env = {"EVENT": "push", "SHA": head, "BEFORE": repo["base"]}
    d = sp.decide(env, repo["root"], REG, {})
    assert d["tasks"] == [] and set(d["skipped_manual"]) == {"f-slow", "iv-slow", "f-slow2", "iv-slow2"}
    # merge advanced scored_sha past that push, remembering the owed manual tasks; slow2 got done
    state = {"scored_sha": head, "pending_manual": ["f-slow", "iv-slow"]}
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": head, "SCOPE": "auto", "INCLUDE_MANUAL": "true"},
                  repo["root"], REG, state)
    assert {t["id"] for t in d["tasks"]} == {"f-slow", "iv-slow"}          # only what is owed
    assert d["skipped_manual"] == []
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": head, "SCOPE": "auto"}, repo["root"], REG, state)
    assert d["tasks"] == []                                                # still not automatic
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": head, "SCOPE": "slow2"}, repo["root"], REG, state)
    assert {t["id"] for t in d["tasks"]} == {"f-slow2", "iv-slow2"}       # explicit: that slug only
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": head, "SCOPE": "all"}, repo["root"], REG, state)
    assert set(d["skipped_manual"]) == {"f-slow", "iv-slow", "f-slow2", "iv-slow2"}   # a full run owes them all


def test_in_progress_coverage_subtracts_only_up_to_date_tasks(repo):
    """Run X is scoring commit A (f-tkd + f-vsharp in flight). A new push B touches vsharp only:
    the planner keeps f-vsharp (X's copy is stale) and drops f-tkd (X covers it at a commit that
    is still current for tkd). A scorer change in A..B breaks every coverage."""
    c = repo["commit"]
    a = c("tkd+vsharp", **{"algorithms/tkd/run.sh": "1\n", "algorithms/vsharp/run.sh": "1\n"})
    b = c("vsharp again", **{"algorithms/vsharp/run.sh": "2\n"})
    tasks = sp.plan_tasks(repo["root"], REG, full=False, slugs=["tkd", "vsharp"])
    others = [{"id": 1, "sha": a, "active": {"f-tkd", "iv-tkd", "f-vsharp"}}]
    keep, dropped = sp.subtract_in_progress(tasks, b, others)
    assert {t["id"] for t in keep} == {"f-vsharp"} and len(dropped) == 2
    # X's task already cancelled/failed → not "active" → not covered
    keep, _ = sp.subtract_in_progress(tasks, b, [{"id": 1, "sha": a, "active": {"f-vsharp"}}])
    assert {t["id"] for t in keep} == {"f-tkd", "iv-tkd", "f-vsharp"}
    # a shard is covered only when nothing scored changed at all; a scorer change breaks everything
    shard = sp.plan_tasks(repo["root"], REG, full=True, slugs=[])
    keep, _ = sp.subtract_in_progress(shard, b, [{"id": 1, "sha": a, "active": {t["id"] for t in shard}}])
    assert {t["id"] for t in keep} == {t["id"] for t in shard if "shard" in t}   # vsharp changed in a..b → shards stale, iv-tkd still covered
    keep, _ = sp.subtract_in_progress(shard, b, [{"id": 1, "sha": b, "active": {t["id"] for t in shard}}])
    assert keep == []                                               # same commit → fully covered
    e = c("scorer", **{"eval/m.py": "3\n"})
    keep, _ = sp.subtract_in_progress(tasks, e, [{"id": 1, "sha": b, "active": {"f-tkd", "iv-tkd", "f-vsharp"}}])
    assert len(keep) == len(tasks)


def test_the_workflow_wires_the_planner_and_never_queues_whole_runs():
    wf = (ROOT / ".github" / "workflows" / "score.yml").read_text()
    assert "python3 scripts/score_plan.py" in wf
    assert "python3 scripts/score_state.py" in wf
    head = wf[: wf.index("jobs:")]
    assert "concurrency:" not in head                               # no workflow-level group: no displacement
    score = wf[wf.index("  score:"):wf.index("  merge:")]
    assert "group: score-${{ matrix.task.id }}" in score and "cancel-in-progress: true" in score
    upload = score[score.index("actions/upload-artifact"):]
    assert "if: always()" in upload and "runs-${{ matrix.task.id }}.done" in upload
    merge = wf[wf.index("  merge:"):]
    assert "always()" in merge.split("steps:")[0]
    assert "results/scoring-state.json" in merge and "Wait for older merges" in merge
    assert "include_manual" in wf
    # rows are stamped with the scoring run, and a newer run's rows/volumes are never overwritten
    assert "QSMCI_RUN: ${{ github.run_id }}.${{ github.run_attempt }}" in score
    drop = merge[merge.index("Drop ids a newer run already scored"):merge.index("Publish volumes")]
    assert "from merge_index import superseded" in drop and "shutil.rmtree" in drop
