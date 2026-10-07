"""qsm_ci/resources.py — the `docker stats` string parsers and the /proc-based sampler.

The resource trace behind the leaderboard's memory/CPU graphs is scraped out of text: engines print
MemUsage as "1.5GiB / 62.8GiB" and CPUPerc as "380.00%", and either field can be "--" while a
container is still coming up. Everything below the regex is best-effort by design — a bad sample must
be skipped, never raised, because profiling may not perturb or sink the run it measures. These tests
pin the unit table, the "--" / unparseable paths that return None, and the apptainer sampler
(`_ProcResourceSampler`), which has no `stats` command to scrape and walks the /proc process tree
instead. `tests/test_resource_sampler.py` covers the OTHER sampler, `qsm_ci.runner._ResourceSampler`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from qsm_ci.resources import (_ProcResourceSampler, _parse_bytes, _parse_cpu_perc,
                              _parse_mem_usage, _stat_fields)

KIB, MIB, GIB, TIB = 1024, 1024 ** 2, 1024 ** 3, 1024 ** 4

needs_proc = pytest.mark.skipif(not Path("/proc/self/stat").exists(),
                                reason="the /proc sampler only exists on Linux")


# ------------------------------------------------------------------------------ _parse_bytes


@pytest.mark.parametrize("tok,expected", [
    ("0B", 0.0),
    ("512MiB", 512 * MIB),
    ("1.2GiB", 1.2 * GIB),
    ("1TiB", 1.0 * TIB),
    ("4KiB", 4 * KIB),
    # The SI units are powers of 1000, not 1024 — docker emits both spellings.
    ("1.5GB", 1.5e9),
    ("7kB", 7e3),
    ("2 GiB", 2.0 * GIB),        # the engine may put a space before the unit
    (" 4KiB ", 4 * KIB),         # surrounding whitespace is stripped
    ("1gib", 1.0 * GIB),         # the unit is matched case-insensitively
])
def test_a_size_token_is_parsed_into_bytes(tok, expected):
    assert _parse_bytes(tok) == pytest.approx(expected)


@pytest.mark.parametrize("tok", ["--", "", "   ", "100", "N/A", "GiB", "1.2.3GiB"])
def test_an_unparseable_size_token_is_none_rather_than_an_error(tok):
    """A unitless number, docker's "--" placeholder and a malformed figure all yield None, which the
    sampler reads as "skip this tick". "1.2.3GiB" gets through the regex but not float() — the
    ValueError branch must return None too."""
    assert _parse_bytes(tok) is None


def test_an_unknown_unit_is_treated_as_plain_bytes():
    """Unknown suffix -> multiplier 1. Pinned because it is a silent fallback, not an error path: a
    future unit nobody mapped is under-reported rather than dropped."""
    assert _parse_bytes("5XB") == 5.0


# -------------------------------------------------------------------------- _parse_mem_usage


@pytest.mark.parametrize("field,expected", [
    ("1.5GiB / 62.8GiB", 1.5 * GIB),
    ("  3.0GB  /  8GB  ", 3e9),
    ("512MiB", 512 * MIB),        # no limit side at all
])
def test_mem_usage_takes_the_used_side_of_the_slash(field, expected):
    """MemUsage is "<used> / <limit>"; reading the limit would report the HOST's memory as the run's."""
    assert _parse_mem_usage(field) == pytest.approx(expected)


def test_a_placeholder_mem_usage_is_none():
    assert _parse_mem_usage("-- / --") is None


# --------------------------------------------------------------------------- _parse_cpu_perc


@pytest.mark.parametrize("field,expected", [
    ("0.00%", 0.0),
    ("100%", 1.0),
    ("380.00%", 3.8),             # CPUPerc is summed across cores, so >100% is real parallelism
    (" 12.5 % ", 0.125),
])
def test_cpu_percent_becomes_cores(field, expected):
    assert _parse_cpu_perc(field) == pytest.approx(expected)


@pytest.mark.parametrize("field", ["--", "", "n/a"])
def test_an_unparseable_cpu_percent_is_none_rather_than_an_error(field):
    assert _parse_cpu_perc(field) is None


# ------------------------------------------------------------------------------- _stat_fields


@needs_proc
def test_stat_fields_are_indexed_from_after_the_comm():
    """Index 0 is state and index 1 is ppid, i.e. the pid and comm columns have been dropped."""
    f = _stat_fields(os.getpid())
    assert f is not None and len(f) > 12
    assert int(f[1]) == os.getppid()
    assert f[0].isalpha()                       # the single-letter state (R/S/D/...)


def test_an_unreadable_stat_file_is_none():
    assert _stat_fields(4194300) is None        # above the default pid_max; no such process


def test_a_comm_containing_spaces_and_parens_does_not_shift_the_fields(monkeypatch):
    """The comm column is arbitrary text in parens, so the split has to start after the FINAL ')'.
    Splitting on whitespace would make every field after a process named like "(ba d) ((x)" wrong."""
    import qsm_ci.resources as resources

    class _Fake:
        def read(self):
            return "4242 ((ba d) ((x)) R 99 1 2 3 4 5 6 7 8 9 1234 5678 0 0"

    monkeypatch.setattr(resources, "open", lambda *a, **kw: _Fake(), raising=False)
    f = _stat_fields(4242)
    assert f[0] == "R" and f[1] == "99"
    assert (f[11], f[12]) == ("1234", "5678")   # utime, stime


# ------------------------------------------------------------------------ _ProcResourceSampler


def test_the_stop_signal_does_not_shadow_thread_stop():
    """Same invariant as runner._ResourceSampler: threading.Thread has a private `_stop()` that
    join() calls, so an instance attribute of that name breaks join() and turns every sampled run
    into a DNF. The Event lives under `_stop_event`."""
    s = _ProcResourceSampler(os.getpid(), "unused.json", interval=0.1)
    assert "_stop" not in vars(s), "must not shadow threading.Thread's internal _stop"
    assert "_stop_event" in vars(s)


@needs_proc
def test_the_first_sample_reports_memory_but_no_cpu_yet():
    """CPU is a delta of utime+stime between ticks, so the first tick has nothing to subtract from
    and must report 0 cores rather than the process's whole lifetime of CPU time."""
    s = _ProcResourceSampler(os.getpid(), "unused.json", interval=0.1)
    assert s._sample() is True
    assert s.mem_bytes[0] > 0                   # the running interpreter has resident pages
    assert s.cpu_cores == [0.0]


@needs_proc
def test_later_samples_derive_cpu_cores_and_stay_aligned_with_memory():
    s = _ProcResourceSampler(os.getpid(), "unused.json", interval=0.1)
    s._sample()
    sum(i * i for i in range(500_000))          # burn a little CPU between the two ticks
    assert s._sample() is True
    assert len(s.mem_bytes) == len(s.cpu_cores) == 2
    assert all(c >= 0.0 for c in s.cpu_cores)   # never negative, even if a child exited


@needs_proc
def test_a_dead_root_pid_yields_no_samples_instead_of_raising():
    s = _ProcResourceSampler(4194300, "unused.json", interval=0.1)
    assert s._sample() is False
    assert s.mem_bytes == [] and s.cpu_cores == []


@needs_proc
def test_the_tree_includes_descendants_not_just_the_root():
    """The whole point of this sampler: apptainer's real work happens in child processes, so summing
    only the root's RSS would report almost nothing."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        deadline = time.time() + 5
        pids: list = []
        while time.time() < deadline:
            pids = _ProcResourceSampler(os.getpid(), "unused.json")._tree_pids()
            if child.pid in pids:
                break
            time.sleep(0.1)
        assert os.getpid() in pids
        assert child.pid in pids
    finally:
        child.terminate()
        child.wait(timeout=10)


@needs_proc
def test_the_lifecycle_writes_a_proc_labelled_trace(tmp_path):
    out = tmp_path / "resources.json"
    s = _ProcResourceSampler(os.getpid(), out, interval=0.1)
    s.start()
    time.sleep(0.3)
    s.stop()
    s.join(timeout=6)
    assert not s.is_alive()
    s.write()

    doc = json.loads(out.read_text())
    assert doc["sampler"] == "proc" and doc["runner"] == "apptainer"
    # The pipeline consumes this shape identically to the docker-stats sampler's.
    assert len(doc["t"]) == len(doc["mem_bytes"]) == len(doc["cpu_cores"])
    assert doc["mem_peak_bytes"] == max(doc["mem_bytes"])
    assert doc["cpu_cores_max"] >= 0 and doc["cpu_cores_avg"] >= 0


def test_an_empty_series_still_writes_zeroed_summaries(tmp_path):
    """max() of an empty list is a ValueError; a run too short to sample must still leave a file the
    pipeline can read."""
    out = tmp_path / "resources.json"
    s = _ProcResourceSampler(4194300, out, interval=0.1)
    s.write()
    doc = json.loads(out.read_text())
    assert doc["mem_peak_bytes"] == 0 and doc["cpu_cores_max"] == 0 and doc["cpu_cores_avg"] == 0
    assert doc["t"] == [] and doc["mem_bytes"] == []


def test_an_unwritable_destination_is_swallowed(tmp_path):
    """Profiling is best-effort: a bad --resources-out path may not take the run down with it."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    s = _ProcResourceSampler(os.getpid(), blocker / "resources.json", interval=0.1)
    s.write()                                   # must not raise
    assert blocker.read_text() == "not a directory"
