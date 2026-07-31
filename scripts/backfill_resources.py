#!/usr/bin/env python3
"""Backfill the resource summary (peak memory, avg + peak CPU) onto every run in results/index.json.

Going forward pipeline.py stamps these onto each row at scoring time (from the run's resources.json).
This one-off populates the runs that were scored before that existed, by reading each run's resource
trace — the local results/<id>/resources.json if present, else the published `resources_url`.

Idempotent and re-runnable: a run that already carries `cpu_cores_avg` is skipped unless --force, so
after a CI rescore lands you can simply re-run this to fill in the freshly-scored runs.

  python scripts/backfill_resources.py [--force] [--workers N]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "results" / "index.json"

FIELDS = ("mem_peak_bytes", "cpu_cores_avg", "cpu_cores_max")


def _summary(doc: dict) -> dict:
    """The three scalar fields from a resources.json (computing them from the series if a summary key
    is absent — older traces predate cpu_cores_avg)."""
    cpu = doc.get("cpu_cores") or []
    mem = doc.get("mem_bytes") or []
    peak = doc.get("mem_peak_bytes") or (max(mem) if mem else 0)
    avg = doc.get("cpu_cores_avg")
    if avg is None:
        avg = (sum(cpu) / len(cpu)) if cpu else 0
    cmax = doc.get("cpu_cores_max") or (max(cpu) if cpu else 0)
    out = {}
    if peak:
        out["mem_peak_bytes"] = int(peak)
    if avg:
        out["cpu_cores_avg"] = round(float(avg), 4)
    if cmax:
        out["cpu_cores_max"] = round(float(cmax), 4)
    return out


def _load_trace(run: dict) -> "dict | None":
    """A run's resource trace: local results/<id>/resources.json first, else its published URL."""
    local = ROOT / "results" / run.get("id", "") / "resources.json"
    if local.exists():
        try:
            return json.loads(local.read_text())
        except Exception:  # noqa: BLE001
            pass
    url = run.get("resources_url")
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception:  # noqa: BLE001 — a missing/bad trace just leaves this run unstamped
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch even runs that already have the fields")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    doc = json.loads(INDEX.read_text())
    runs = doc.get("runs", [])
    todo = [r for r in runs if (args.force or "cpu_cores_avg" not in r) and (r.get("status") == "ok")]
    print(f"{len(runs)} runs; {len(todo)} to backfill "
          f"({sum('cpu_cores_avg' in r for r in runs)} already have it)")

    def work(run):
        trace = _load_trace(run)
        if not trace:
            return run.get("id"), False
        s = _summary(trace)
        if not s:
            return run.get("id"), False
        run.update(s)
        return run.get("id"), True

    done = miss = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, (rid, ok) in enumerate(pool.map(work, todo), 1):
            done += ok
            miss += not ok
            if i % 100 == 0:
                print(f"  ...{i}/{len(todo)}", file=sys.stderr)

    INDEX.write_text(json.dumps(doc, indent=2) + "\n")
    cov = sum("cpu_cores_avg" in r for r in runs)
    print(f"stamped {done}, no-trace {miss}. Coverage now {cov}/{len(runs)} runs -> {INDEX}")


if __name__ == "__main__":
    main()
