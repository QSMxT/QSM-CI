"""Regression guard for the resource sampler (the CPU/memory-over-time trace behind the graphs).

_ResourceSampler subclasses threading.Thread. threading.Thread has a private `_stop()` method that
join() calls internally, so an instance attribute named `_stop` shadows it and makes join() raise
`TypeError: 'Event' object is not callable`. That fired in _run_container's finally block AFTER the
container had run fine, so pipeline.py recorded EVERY containerized run as a DNF and no resources.json
was written. These tests pin the fix: the stop signal must not shadow Thread._stop, and the full
start/stop/join/write lifecycle must complete and emit a valid trace.
"""
import json
import time

from qsm_ci.runner import _ResourceSampler


def test_stop_signal_does_not_shadow_thread_stop():
    """The sampler must not put a `_stop` attribute on the instance.

    threading.Thread uses a private `_stop()` method internally in join() (the exact name/existence
    varies by CPython version), so an instance attribute named `_stop` shadows it and breaks join().
    The version-robust invariant is simply: don't create one. The stop Event lives under `_stop_event`.
    """
    s = _ResourceSampler("no-such-container", "docker", "unused.json", interval=0.1)
    assert "_stop" not in vars(s), "must not shadow threading.Thread's internal _stop"
    assert "_stop_event" in vars(s)


def test_lifecycle_join_and_write(tmp_path):
    """start -> stop -> join -> write completes without TypeError and writes a valid JSON trace.

    Uses a container name that doesn't exist, so `<engine> stats` just yields empty samples — we're
    exercising the thread lifecycle (the part that regressed), not real sampling.
    """
    out = tmp_path / "resources.json"
    s = _ResourceSampler("no-such-container", "docker", out, interval=0.1)
    s.start()
    time.sleep(0.25)
    s.stop()
    s.join(timeout=6)          # regressed here: TypeError: 'Event' object is not callable
    assert not s.is_alive()    # join actually joined
    s.write()

    doc = json.loads(out.read_text())
    for key in ("t", "mem_bytes", "cpu_cores"):
        assert key in doc and isinstance(doc[key], list)
