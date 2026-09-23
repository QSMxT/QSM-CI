"""qsm_ci/containers.py — runner probing and how the invoking user is mapped into the container.

The docker path used to call `os.getuid()` unconditionally (an AttributeError on Windows) and always
pass `--user <uid>:<gid>`, which is wrong under a rootless daemon: the host user is already uid 0
inside the namespace, so that uid is unmapped and every write to the /output bind mount fails. The
daemon probe also had no timeout, so a wedged daemon hung the CLI instead of falling through.
"""
from __future__ import annotations

import subprocess

import pytest

from qsm_ci import containers


@pytest.fixture(autouse=True)
def _no_cached_probe(monkeypatch):
    """_docker_is_rootless is lru_cached for the process; each test gets a clean answer."""
    containers._docker_is_rootless.cache_clear()
    monkeypatch.delenv("QSMCI_CONTAINER_USER", raising=False)
    yield
    # a test may still have _docker_is_rootless monkeypatched to a plain function here
    getattr(containers._docker_is_rootless, "cache_clear", lambda: None)()


def _probe(monkeypatch, *, stdout="", rc=0, raises=None):
    def fake(cmd, *a, **kw):
        if raises:
            raise raises
        assert "timeout" in kw, f"{cmd[:2]} probes the daemon without a timeout"
        return subprocess.CompletedProcess(cmd, rc, stdout, "")
    monkeypatch.setattr(containers.subprocess, "run", fake)


def test_root_daemon_maps_the_invoking_user(monkeypatch):
    _probe(monkeypatch, stdout="seccomp,apparmor")
    monkeypatch.setattr(containers.os, "getuid", lambda: 1000, raising=False)
    monkeypatch.setattr(containers.os, "getgid", lambda: 1000, raising=False)
    assert containers._user_args("docker") == ["--user", "1000:1000"]


def test_rootless_daemon_gets_no_user_flag(monkeypatch):
    """--user <host uid> under rootless docker makes /output unwritable."""
    _probe(monkeypatch, stdout="name=rootless,seccomp")
    assert containers._user_args("docker") == []


def test_podman_keeps_its_id_mapping(monkeypatch):
    assert containers._user_args("podman") == ["--userns=keep-id"]


def test_non_posix_host_does_not_call_getuid(monkeypatch):
    """os.getuid does not exist on Windows — reaching for it was an AttributeError, not a fallback."""
    _probe(monkeypatch, stdout="")
    monkeypatch.delattr(containers.os, "getuid", raising=False)
    assert containers._user_args("docker") == []


@pytest.mark.parametrize("value,expected", [
    ("off", []), ("none", []), ("NO", []), ("False", []),
    ("1000:1000", ["--user", "1000:1000"]), ("root", ["--user", "root"]),
])
def test_the_env_override_wins(monkeypatch, value, expected):
    monkeypatch.setenv("QSMCI_CONTAINER_USER", value)
    monkeypatch.setattr(containers, "_docker_is_rootless",
                        lambda: pytest.fail("the override must not probe the daemon"))
    assert containers._user_args("docker") == expected


def test_an_unreachable_daemon_is_not_reported_as_rootless(monkeypatch):
    """Unknown falls back to the historical behaviour rather than silently changing the mapping."""
    _probe(monkeypatch, raises=FileNotFoundError())
    assert containers._docker_is_rootless() is False
    containers._docker_is_rootless.cache_clear()
    _probe(monkeypatch, raises=subprocess.TimeoutExpired("docker", 10))
    assert containers._docker_is_rootless() is False


def test_a_wedged_daemon_does_not_hang_check_runner(monkeypatch):
    _probe(monkeypatch, raises=subprocess.TimeoutExpired("docker", 10))
    assert containers.check_runner("docker") is False


def test_check_runner_passes_a_timeout_to_the_probe(monkeypatch):
    _probe(monkeypatch, rc=0)          # the fake asserts `timeout` is present
    assert containers.check_runner("docker") is True
    assert containers.check_runner("local") is True
