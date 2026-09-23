"""repro.yml's `plan` job: where each task runs, and which ones exist at all.

The planner lives inline in the workflow, so these tests extract that block and run it against the
real `algorithms/` tree — the same thing Actions does, minus the runner. Two bugs this pins:

  - `include_gpu=true` sent every heavy method to `['self-hosted','Linux','X64']` with `gpu: '1'`.
    Those are QSM-CI's 31 GB CPU boxes (there is no `gpu` label anywhere), so QSMCI_GPU=1 there
    means `docker --gpus all` on a host with no GPU: the container fails before the method starts.
  - repro had no `ci_skip` filter, so every `ci_skip: true` method got a self-hosted no-op task per
    acquisition on every full run — 4 methods × 23 acquisitions of queue for nothing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "repro.yml"
CPU_LABELS = ["self-hosted", "Linux", "X64"]


@pytest.fixture(scope="module")
def plan_block(tmp_path_factory) -> Path:
    """The `TASKS=$(python3 - <<'PY' … PY` body of the plan job, as a runnable script."""
    m = re.search(r"TASKS=\$\(python3 - <<'PY'\n(.*?)\n          PY\n", WORKFLOW.read_text(), re.S)
    assert m, "could not find the plan job's inline python in repro.yml"
    body = "\n".join(ln[10:] if ln.startswith(" " * 10) else ln for ln in m.group(1).split("\n"))
    p = tmp_path_factory.mktemp("plan") / "plan.py"
    p.write_text(body)
    return p


def _plan(script: Path, *, full: bool, include_gpu: bool, slugs: list[str] | None = None) -> list[dict]:
    env = {**os.environ, "FULL": str(full).lower(), "SLUGS": json.dumps(slugs or []),
           "N": "6", "ACQS": "all", "INCLUDE_GPU": str(include_gpu).lower()}
    r = subprocess.run([sys.executable, str(script)], env=env, cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _spec(slug: str) -> dict:
    doc = yaml.safe_load((ROOT / "algorithms" / slug / "algorithm.yml").read_text())
    return doc if isinstance(doc, dict) else {}


SKIPPED = sorted(p.parent.name for p in (ROOT / "algorithms").glob("*/algorithm.yml")
                 if _spec(p.parent.name).get("ci_skip"))


def test_there_is_something_to_skip():
    """Guards the two tests below from passing vacuously if ci_skip is ever retired."""
    assert SKIPPED, "no ci_skip: true methods — the skip tests would prove nothing"


@pytest.mark.parametrize("include_gpu", [False, True])
def test_gpu_flag_is_only_set_for_tasks_that_asked_for_a_gpu_runner(plan_block, include_gpu):
    for t in _plan(plan_block, full=True, include_gpu=include_gpu):
        if t["gpu"] == "1":
            assert "gpu" in t["runs_on"], f"{t['id']} wants a GPU but is routed to {t['runs_on']}"
        if t["runs_on"] == CPU_LABELS or t["runs_on"] == "ubuntu-latest":
            assert t["gpu"] == "0", f"{t['id']} sets QSMCI_GPU=1 on a runner with no GPU"


def test_gpu_tier_methods_do_route_to_a_gpu_pool(plan_block):
    """The counterpart: the fix must not have silently dropped the GPU methods instead."""
    tasks = _plan(plan_block, full=True, include_gpu=True)
    gpu_slugs = {s for s in (p.parent.name for p in (ROOT / "algorithms").glob("*/algorithm.yml"))
                 if str(_spec(s).get("runner", "")).strip("\"'") in ("manual", "gpu")
                 and not _spec(s).get("ci_skip")}
    assert gpu_slugs, "no manual/gpu-tier methods — nothing to route"
    routed = {t["focus"] for t in tasks if t.get("focus") and t["gpu"] == "1"}
    assert routed == gpu_slugs, f"expected {gpu_slugs} on the gpu pool, got {routed}"


@pytest.mark.parametrize("include_gpu", [False, True])
def test_ci_skipped_methods_never_get_a_task(plan_block, include_gpu):
    for t in _plan(plan_block, full=True, include_gpu=include_gpu):
        assert t.get("focus") not in SKIPPED, f"{t['id']}: {t['focus']} is ci_skip: true"


def test_ci_skipped_methods_are_ignored_even_when_named_in_scope(plan_block):
    """An incremental run's slug list comes from the diff, which does include ci_skip'd methods."""
    tasks = _plan(plan_block, full=False, include_gpu=True, slugs=SKIPPED)
    assert tasks == [], f"planned {len(tasks)} task(s) for ci_skip'd methods: {tasks[:2]}"


def test_skipped_methods_stay_out_of_the_hosted_shard_sweep(plan_block):
    """They are excluded, not merely unscheduled — the sweep must not try to run them either."""
    shard = next(t for t in _plan(plan_block, full=True, include_gpu=False) if "shard" in t)
    excluded = set(shard["exclude"].split(","))
    assert set(SKIPPED) <= excluded, sorted(set(SKIPPED) - excluded)


def test_the_planner_reuses_score_plan_rather_than_its_own_regexes(plan_block):
    """The two tracks drifted on what `runner:` meant because each parsed algorithm.yml itself."""
    src = plan_block.read_text()
    assert "from score_plan import" in src
    assert "re.search" not in src, "a hand-rolled algorithm.yml regex is back in repro.yml"
