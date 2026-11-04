"""scripts/runner_cleanup.py frees disk on the shared self-hosted box while other jobs run, so what it
must NEVER remove matters more than what it does: a non-QSM-CI image, an image a container uses, an
image main pins (unless asked), a parity build whose run is still going, a scratch dir a job is
writing to, or this job's own workspace.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import runner_cleanup as rc  # noqa: E402

NOW = time.time()
DAY = 86400


def _iso(days_ago: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.123456789Z", time.gmtime(NOW - days_ago * DAY))


def _img(id_, *, tags=(), digests=(), created=30, tagged=None):
    return {"Id": id_, "RepoTags": list(tags), "RepoDigests": list(digests), "Created": _iso(created),
            "Metadata": {"LastTagTime": _iso(tagged) if tagged is not None else "0001-01-01T00:00:00Z"}}


def _verdict(img, *, in_use=(), pinned=(), drop_pinned=False, finished=None):
    return rc.image_verdict(img, in_use=set(in_use), pinned=set(pinned), now=NOW, days=7,
                            drop_pinned=drop_pinned, run_finished=finished or (lambda r: None))


Q = rc.QSMCI_PREFIX


def test_only_unused_unpinned_old_qsmci_images_go():
    old = _img("sha256:a", digests=[Q + "tkd@sha256:1"], created=30)
    assert _verdict(old)[0] is True
    assert _verdict(_img("sha256:b", tags=["ubuntu:24.04"], created=300))[0] is False      # not ours
    assert _verdict(old, in_use={"sha256:a"}) == (False, "used by a container")
    assert _verdict(old, pinned={Q + "tkd@sha256:1"}) == (False, "pinned on main")
    assert _verdict(old, pinned={Q + "tkd@sha256:1"}, drop_pinned=True)[0] is True
    assert _verdict(old, pinned={Q + "tkd@sha256:1"}, drop_pinned=True, in_use={"sha256:a"})[0] is False
    # "used" = pulled/tagged recently: LastTagTime wins over an old Created
    assert _verdict(_img("sha256:c", digests=[Q + "x@sha256:2"], created=90, tagged=1))[0] is False
    assert _verdict(_img("sha256:d", digests=[Q + "x@sha256:3"], created=3))[0] is False


def test_parity_builds_go_once_their_run_finished():
    b = _img("sha256:p", tags=["qsmxt-under-test:123", "qsmxt-under-test:123-models"], created=1)
    assert _verdict(b, finished=lambda r: True)[0] is True
    assert _verdict(b, finished=lambda r: False)[0] is False                  # still running
    assert _verdict(b, finished=lambda r: None)[0] is False                   # unknown: keep
    assert _verdict(_img("sha256:q", tags=["qsmxt-under-test:9"], created=10), finished=lambda r: None)[0] is True
    assert _verdict(b, finished=lambda r: True, in_use={"sha256:p"})[0] is False
    assert rc.under_test_run("qsmxt-under-test:42-models") == "42" and rc.under_test_run("qsmxt-under-test:x") is None
    assert rc.under_test_run("qsmxt-under-test:42-j3-models") == "42" == rc.under_test_run("qsmxt-under-test:42-j0")


def test_pinned_refs_match_what_the_algorithms_pin():
    pinned = rc.pinned_refs(ROOT / "algorithms")
    spec = yaml.safe_load((ROOT / "algorithms" / "tkd-qsmrs" / "algorithm.yml").read_text())
    assert spec["image"] in pinned and all(" " not in p and "#" not in p for p in pinned)


def _touch(p: Path, days_ago: float) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("x")
    t = NOW - days_ago * DAY
    os.utime(p, (t, t))


def _runner(base: Path, name: str, repo: str = "QSMxT/QSM-CI") -> Path:
    r = base / name
    (r / "_work").mkdir(parents=True)
    (r / ".runner").write_text("\ufeff" + json.dumps({"gitHubUrl": f"https://github.com/{repo}"}),
                               encoding="utf-8")
    return r


def test_scratch_goes_only_when_idle_and_never_from_this_jobs_workspace(tmp_path):
    me, sib = _runner(tmp_path, "actions-runner-QSM-CI-1"), _runner(tmp_path, "actions-runner-QSM-CI-2")
    (tmp_path / "not-a-runner" / "_work").mkdir(parents=True)
    # The box is shared: other projects' runners are never ours to clean.
    _runner(tmp_path, "actions-runner-QSMxT-1", "QSMxT/QSMxT")
    _runner(tmp_path, "actions-runner-neurocontainers-1", "NeuroDesk/neurocontainers")
    assert rc.runner_roots(me) == [me, sib]
    own_ws = me / "_work" / "QSM-CI" / "QSM-CI"
    _touch(own_ws / ".work" / "old.nii", 10)                   # this job's workspace: never
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / ".work" / "a" / "old.nii", 10)
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / ".work" / "a", 10)     # a new subdir counts as activity
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / ".work", 10)
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / ".parity" / "old.nii", 10)
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / ".parity" / "deep" / "new.nii", 0.1)   # a job is writing
    _touch(sib / "_work" / "_temp" / "x" / ".work" / "old", 10)                       # runner internals
    _touch(sib / "_work" / "QSM-CI" / "QSM-CI" / "data" / "old.nii", 10)              # not scratch
    got = rc.stale_scratch(rc.runner_roots(me), own_ws, NOW, 2)
    assert got == [sib / "_work" / "QSM-CI" / "QSM-CI" / ".work"]


def test_diag_logs_older_than_a_week(tmp_path):
    r = _runner(tmp_path, "actions-runner-QSM-CI-1")
    for name, age in (("Runner_old.log", 30), ("Worker_new.log", 1), ("pages/old.log", 9), ("keep.txt", 30)):
        _touch(r / "_diag" / name, age)
    assert {p.name for p in rc.old_diag([r], NOW, 7)} == {"Runner_old.log", "old.log"}


def test_the_workflow_runs_on_the_self_hosted_runners_weekly_and_on_dispatch():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "runner-cleanup.yml").read_text())
    on = wf[True]   # PyYAML reads the `on:` key as boolean True
    assert on["schedule"] and "workflow_dispatch" in on
    job = wf["jobs"]["clean"]
    assert "self-hosted" in job["runs-on"] and "vars.QSMCI_SELFHOSTED_LABELS" in str(job["strategy"])
    text = (ROOT / ".github" / "workflows" / "runner-cleanup.yml").read_text()
    assert text.index("Disk before") < text.index("python3 scripts/runner_cleanup.py") < text.index("Disk after")
    assert "df -h" in text
    src = (ROOT / "scripts" / "runner_cleanup.py").read_text()
    assert '["docker", "rmi", *refs]' in src and '"rmi", "-f"' not in src and "--force" not in src


def test_stale_qsm_ci_temp_dirs_go_and_others_stay(tmp_path):
    _touch(tmp_path / "qsm-ci-abc" / "input" / "phase.nii", 5)
    _touch(tmp_path / "qsm-ci-abc" / "input", 5)
    _touch(tmp_path / "qsm-ci-abc", 5)
    _touch(tmp_path / "qsm-ci-live" / "output" / "chi.nii", 0.2)       # a run in progress
    _touch(tmp_path / "other" / "old", 30)                              # not ours
    assert rc.stale_tmp(tmp_path, NOW, 2) == [tmp_path / "qsm-ci-abc"]


def test_no_global_docker_prune():
    # The daemon is shared with other projects' runners: only QSM-CI's own images/containers go.
    src = (Path(__file__).resolve().parent.parent / "scripts" / "runner_cleanup.py").read_text()
    assert '"image", "prune"' not in src and '"builder", "prune"' not in src


def test_each_parity_job_removes_its_own_build_image():
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "parity.yml").read_text()
    assert "qsmxt-under-test:${{ github.run_id }}-j${{ strategy.job-index }}" in wf
    step = wf.split("name: Remove this job's qsmxt image", 1)[1].split("\n      - ", 1)[0]
    assert "always()" in step and 'docker rmi "$IMG"' in step
