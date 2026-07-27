"""Resource-usage sampler for containerised runs.

While a container runs we poll `<engine> stats <name>` on an interval and record a time series of
memory (bytes) and CPU (cores). Kept dependency-free (regex + subprocess) like the rest of the
runner, and deliberately defensive: profiling must never perturb or sink the run it measures.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path


_MEM_UNITS = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12,
              "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4}


def _parse_bytes(tok: str) -> "float | None":
    """"1.2GiB" / "512MiB" / "0B" -> bytes. None if unparseable (docker sometimes emits "--")."""
    tok = tok.strip()
    m = re.match(r"^([0-9.]+)\s*([A-Za-z]+)$", tok)
    if not m:
        return None
    val, unit = m.group(1), m.group(2).upper()
    try:
        return float(val) * _MEM_UNITS.get(unit, 1)
    except ValueError:
        return None


def _parse_mem_usage(field: str) -> "float | None":
    """docker/podman `stats` MemUsage is "<used> / <limit>"; we want the used side in bytes."""
    used = field.split("/")[0]
    return _parse_bytes(used)


def _parse_cpu_perc(field: str) -> "float | None":
    """"380.00%" -> 3.8 cores (CPUPerc is summed across cores, so >100% means multi-core)."""
    field = field.strip().rstrip("%").strip()
    try:
        return float(field) / 100.0
    except ValueError:
        return None


class _ResourceSampler(threading.Thread):
    """Poll `<engine> stats <name>` on an interval while a container runs, recording a time series of
    memory (bytes) and CPU (cores). A single bad/empty sample is skipped, never raised — the sampler
    must not perturb the run it's measuring. On stop() the series is written to `out_path` as JSON."""

    def __init__(self, name: str, engine: str, out_path: Path, interval: float = 1.0):
        super().__init__(daemon=True)
        self.name, self.engine, self.out_path, self.interval = name, engine, Path(out_path), interval
        # NB: must NOT be named `_stop` — threading.Thread has a private `_stop()` method that join()
        # calls internally; shadowing it with an Event breaks join() ("'Event' object is not callable")
        # and made every sampled run crash -> DNF.
        self._stop_event = threading.Event()
        self.t, self.mem_bytes, self.cpu_cores = [], [], []

    def _sample(self):
        try:
            r = subprocess.run(
                [self.engine, "stats", self.name, "--no-stream",
                 "--format", "{{.MemUsage}}|{{.CPUPerc}}"],
                capture_output=True, text=True, timeout=5)
        except Exception:  # noqa: BLE001 — engine hiccup / container not up yet; skip this tick
            return
        if r.returncode != 0:
            return
        line = (r.stdout or "").strip().splitlines()
        if not line:
            return
        parts = line[0].split("|")
        if len(parts) != 2:
            return
        mem = _parse_mem_usage(parts[0])
        cpu = _parse_cpu_perc(parts[1])
        if mem is None or cpu is None:
            return
        self.mem_bytes.append(mem)
        self.cpu_cores.append(cpu)

    def run(self):
        t0 = time.time()
        # Poll immediately, then every `interval` seconds until stopped — so even a very short run
        # (0–2 samples) records something rather than nothing.
        while not self._stop_event.is_set():
            before = time.time()
            self._sample()
            if self.mem_bytes:  # only timestamp accepted samples, so t/mem/cpu stay aligned
                if len(self.t) < len(self.mem_bytes):
                    self.t.append(round(before - t0, 3))
            elapsed = time.time() - before
            self._stop_event.wait(max(0.0, self.interval - elapsed))

    def stop(self):
        self._stop_event.set()

    def write(self):
        try:
            self.out_path.parent.mkdir(parents=True, exist_ok=True)
            doc = {
                "interval_s": self.interval,
                "t": self.t,
                "mem_bytes": self.mem_bytes,
                "cpu_cores": self.cpu_cores,
                "mem_peak_bytes": max(self.mem_bytes) if self.mem_bytes else 0,
                "cpu_cores_max": max(self.cpu_cores) if self.cpu_cores else 0,
                "sampler": "docker-stats",
                "runner": self.engine,
            }
            self.out_path.write_text(json.dumps(doc))
        except Exception:  # noqa: BLE001 — profiling is best-effort; never sink the run over it
            pass


_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def _stat_fields(pid: int) -> "list | None":
    """Fields of /proc/<pid>/stat AFTER pid+comm, so index 0 = state, 1 = ppid, 11 = utime, 12 = stime
    (comm can contain spaces/parens, so split after the final ')')."""
    try:
        data = open(f"/proc/{pid}/stat").read()
    except OSError:
        return None
    r = data.rfind(")")
    return data[r + 2:].split() if r != -1 else None


class _ProcResourceSampler(threading.Thread):
    """Resource sampler for runners without a `stats` command (apptainer): polls /proc for the whole
    process TREE rooted at `root_pid`, summing RSS (bytes) and deriving CPU (cores) from utime+stime
    deltas. Same output shape as _ResourceSampler so the pipeline consumes it identically. Best-effort:
    a bad read is skipped, never raised."""

    def __init__(self, root_pid: int, out_path: Path, interval: float = 1.0):
        super().__init__(daemon=True)
        self.root_pid, self.out_path, self.interval = root_pid, Path(out_path), interval
        self._stop_event = threading.Event()
        self.t, self.mem_bytes, self.cpu_cores = [], [], []
        self._prev_ticks = None
        self._prev_time = None

    def _tree_pids(self) -> list:
        """root_pid + all descendants, via the ppid links in /proc."""
        children: dict = {}
        try:
            entries = [int(e) for e in os.listdir("/proc") if e.isdigit()]
        except OSError:
            return [self.root_pid]
        for pid in entries:
            f = _stat_fields(pid)
            if f and len(f) > 1:
                try:
                    children.setdefault(int(f[1]), []).append(pid)
                except ValueError:
                    pass
        pids, stack = [], [self.root_pid]
        while stack:
            p = stack.pop()
            pids.append(p)
            stack.extend(children.get(p, []))
        return pids

    def _sample(self):
        rss, ticks = 0, 0
        for pid in self._tree_pids():
            try:
                rss += int(open(f"/proc/{pid}/statm").read().split()[1]) * _PAGE_SIZE  # resident pages
            except (OSError, IndexError, ValueError):
                pass
            f = _stat_fields(pid)
            if f and len(f) > 12:
                try:
                    ticks += int(f[11]) + int(f[12])  # utime + stime
                except ValueError:
                    pass
        now = time.time()
        cpu = 0.0
        if self._prev_ticks is not None and now > self._prev_time:
            cpu = (ticks - self._prev_ticks) / _CLK_TCK / (now - self._prev_time)
        self._prev_ticks, self._prev_time = ticks, now
        if rss > 0:
            self.mem_bytes.append(rss)
            self.cpu_cores.append(round(max(cpu, 0.0), 3))
            return True
        return False

    def run(self):
        t0 = time.time()
        while not self._stop_event.is_set():
            before = time.time()
            if self._sample() and len(self.t) < len(self.mem_bytes):
                self.t.append(round(before - t0, 3))
            self._stop_event.wait(max(0.0, self.interval - (time.time() - before)))

    def stop(self):
        self._stop_event.set()

    def write(self):
        try:
            self.out_path.parent.mkdir(parents=True, exist_ok=True)
            self.out_path.write_text(json.dumps({
                "interval_s": self.interval,
                "t": self.t,
                "mem_bytes": self.mem_bytes,
                "cpu_cores": self.cpu_cores,
                "mem_peak_bytes": max(self.mem_bytes) if self.mem_bytes else 0,
                "cpu_cores_max": max(self.cpu_cores) if self.cpu_cores else 0,
                "sampler": "proc",
                "runner": "apptainer",
            }))
        except Exception:  # noqa: BLE001 — profiling is best-effort; never sink the run over it
            pass
