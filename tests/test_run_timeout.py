"""Per-run wall-clock enforcement (CONTRACT.md: "Default 2 h wall-clock; exceeding it is a DNF").

Before this, no subprocess in the run chain carried a timeout, so the only thing bounding a wedged
submission was the GitHub job cap — which kills the whole shard: the other runs sharing it produce
no rows at all (not even DNFs), and on a self-hosted box the container outlives the killed client
and keeps holding memory. These tests pin the three pieces that fix that: where the budget comes
from, that an over-budget run dies with its whole process tree, and that it surfaces as a DNF row
for that one run rather than an exception out of the shard.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

from qsm_ci import containers


# ---------------------------------------------------------------------------------------------------
# Where the budget comes from
# ---------------------------------------------------------------------------------------------------

def test_default_is_the_two_hour_contract_limit(monkeypatch):
    monkeypatch.delenv("QSMCI_TIMEOUT", raising=False)
    assert containers.timeout_s() == containers.DEFAULT_TIMEOUT_S == 7200.0


def test_env_var_is_seconds_and_overrides_the_default(monkeypatch):
    monkeypatch.setenv("QSMCI_TIMEOUT", "90")
    assert containers.timeout_s() == 90.0


def test_per_method_minutes_beat_the_env_var(monkeypatch):
    """`timeout_minutes:` in algorithm.yml is the per-method escape hatch for a slow inversion."""
    monkeypatch.setenv("QSMCI_TIMEOUT", "90")
    assert containers.timeout_s(240) == 240 * 60.0


@pytest.mark.parametrize("src", ["env", "method"])
def test_zero_disables_the_cap(monkeypatch, src):
    """A human driving a long run by hand is their own supervisor; 0 means "no limit"."""
    if src == "env":
        monkeypatch.setenv("QSMCI_TIMEOUT", "0")
        assert containers.timeout_s() is None
    else:
        assert containers.timeout_s(0) is None


def test_garbage_env_falls_back_to_the_default_rather_than_crashing(monkeypatch):
    monkeypatch.setenv("QSMCI_TIMEOUT", "two hours")
    assert containers.timeout_s() == containers.DEFAULT_TIMEOUT_S


# ---------------------------------------------------------------------------------------------------
# An over-budget run is killed, tree and all
# ---------------------------------------------------------------------------------------------------

def _sleeper(tmp_path: Path, marker: Path) -> dict:
    """A method whose run.sh backgrounds a child that outlives its parent unless the GROUP is killed.

    The child appends to `marker` a second after the group should already be gone, so a surviving
    child is visible as a non-empty file rather than as a flaky timing assertion.
    """
    d = tmp_path / "sleeper"
    d.mkdir()
    (d / "run.sh").write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        ( sleep 4; echo survived >> {marker} ) &
        sleep 60
    """))
    return {"dir": d, "name": "Sleeper"}


def test_local_run_over_budget_kills_the_whole_process_tree(tmp_path):
    marker = tmp_path / "survivors.txt"
    algo = _sleeper(tmp_path, marker)
    t0 = time.time()
    with pytest.raises(containers.RunTimeout) as exc:
        containers._run_container(algo, tmp_path / "in", tmp_path / "out", "local",
                                  lambda *a: None, timeout=1.0)
    elapsed = time.time() - t0
    assert elapsed < 30, f"the 60 s sleep was not cut short (took {elapsed:.1f}s)"
    assert "wall-clock" in str(exc.value) or "CONTRACT" in str(exc.value)
    time.sleep(5)
    assert not marker.exists(), "a backgrounded child outlived the kill — only the leader was killed"


def test_a_run_inside_its_budget_is_untouched(tmp_path):
    d = tmp_path / "quick"
    d.mkdir()
    (d / "run.sh").write_text("#!/usr/bin/env bash\ntrue\n")
    rt = containers._run_container({"dir": d, "name": "Quick"}, tmp_path / "in", tmp_path / "out",
                                   "local", lambda *a: None, timeout=60.0)
    assert rt >= 0


def test_oci_timeout_kills_the_container_by_name_not_just_the_client(monkeypatch, tmp_path):
    """`subprocess.run(timeout=)` kills the docker CLIENT; `--rm` only cleans up after exit, so the
    container keeps running and holding the runner's memory. The engine must be told to kill it."""
    killed: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        if cmd[:2] == ["docker", "kill"]:
            killed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout") or 1)

    monkeypatch.setattr(containers, "_build_oci", lambda *a, **kw: "img:latest")
    monkeypatch.setattr(containers, "_user_args", lambda r: [])
    monkeypatch.setattr(containers.subprocess, "run", fake_run)
    with pytest.raises(containers.RunTimeout):
        containers._run_container({"dir": tmp_path, "name": "X"}, tmp_path / "in", tmp_path / "out",
                                  "docker", lambda *a: None, timeout=1.0)
    assert killed, "the container was never killed — it would outlive the run"
    assert killed[0][2].startswith("qsm-ci-"), killed


def test_the_run_command_actually_carries_the_timeout(monkeypatch, tmp_path):
    """Guards the regression the issue describes: a `subprocess.run` in the chain with no timeout."""
    seen = {}

    def fake_run(cmd, *a, **kw):
        if cmd[:2] != ["docker", "kill"]:
            seen["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(containers, "_build_oci", lambda *a, **kw: "img:latest")
    monkeypatch.setattr(containers, "_user_args", lambda r: [])
    monkeypatch.setattr(containers.subprocess, "run", fake_run)
    containers._run_container({"dir": tmp_path, "name": "X"}, tmp_path / "in", tmp_path / "out",
                              "docker", lambda *a: None, timeout=1234.0)
    assert seen["timeout"] == 1234.0


# ---------------------------------------------------------------------------------------------------
# The scorer records it as a DNF for THAT run
# ---------------------------------------------------------------------------------------------------

def test_scorer_run_algo_raises_a_short_timeout_error(pipeline, tmp_path, monkeypatch):
    """`dnf_reason` is shown on the leaderboard, so it must be a sentence — not a repr of the argv,
    which is what bare `subprocess.TimeoutExpired` stringifies to."""
    marker = tmp_path / "survivors.txt"
    algo = _sleeper(tmp_path, marker)
    monkeypatch.setenv("QSMCI_TIMEOUT", "1")
    with pytest.raises(TimeoutError) as exc:
        pipeline.run_algo(algo, tmp_path / "in", tmp_path / "out", runner="local")
    msg = str(exc.value)
    assert "timed out" in msg and len(msg) < 200, msg
    assert "/tmp" not in msg and "run.sh" not in msg, f"argv leaked into dnf_reason: {msg}"


def test_per_method_timeout_minutes_is_read_from_the_algorithm_spec(pipeline, tmp_path, monkeypatch):
    """A method that declares a longer budget is not cut off at the env-var value."""
    d = tmp_path / "quick"
    d.mkdir()
    (d / "run.sh").write_text("#!/usr/bin/env bash\nsleep 2\n")
    monkeypatch.setenv("QSMCI_TIMEOUT", "1")   # would kill it...
    pipeline.run_algo({"dir": d, "name": "Q", "timeout_minutes": 5},   # ...but the method overrides
                      tmp_path / "in", tmp_path / "out", runner="local")


def test_no_cap_is_handed_to_the_cli_explicitly_not_by_omission(pipeline, tmp_path, monkeypatch):
    """`timeout_minutes: 0` means "no cap". The scorer passes os.environ down to `qsm-ci run`, so
    leaving $QSMCI_TIMEOUT to be inherited would let an ambient value silently re-impose one."""
    seen = {}
    monkeypatch.setenv("QSMCI_TIMEOUT", "60")

    class _Fake:
        args = ["qsm-ci"]

        def __init__(self, *a, **kw):
            seen.update(kw.get("env") or {})

        def wait(self, timeout=None):
            seen["budget"] = timeout
            return 0

    monkeypatch.setattr(pipeline.subprocess, "Popen", _Fake)
    pipeline.run_algo({"dir": tmp_path, "name": "N", "slug": "n", "consumes": [], "produces": ["chimap"],
                       "timeout_minutes": 0}, tmp_path / "in", tmp_path / "out", runner="docker")
    assert seen["QSMCI_TIMEOUT"] == "0", seen.get("QSMCI_TIMEOUT")
    assert seen["budget"] is None


def test_discovery_carries_timeout_minutes_through(pipeline):
    """The budget is useless if discover_algorithms drops the key on the way to run_algo."""
    algos = pipeline.discover_algorithms("sim", None)
    assert algos, "no algorithms discovered"
    assert all("timeout_minutes" in a for a in algos)
    declared = {a["slug"]: a["timeout_minutes"] for a in algos if a["timeout_minutes"]}
    for slug, minutes in declared.items():
        spec = (Path(pipeline.ROOT) / "algorithms" / slug / "algorithm.yml").read_text()
        assert f"timeout_minutes: {minutes}" in spec, slug


def test_contract_documents_the_limit_this_code_enforces():
    """The 2 h in CONTRACT.md and DEFAULT_TIMEOUT_S are one promise; don't let them drift."""
    text = (Path(__file__).resolve().parent.parent / "CONTRACT.md").read_text()
    assert "2 h wall-clock" in text
    assert containers.DEFAULT_TIMEOUT_S == 2 * 3600


@pytest.mark.skipif(os.name == "nt", reason="process groups are POSIX")
def test_kill_process_tree_is_safe_on_an_already_dead_process(tmp_path):
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    containers._kill_process_tree(proc, lambda *a: None)   # must not raise
