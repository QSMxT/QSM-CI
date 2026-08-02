#!/usr/bin/env python3
"""Drop orphaned `tuned` runs from results/index.json.

A published isolated `tuned` run is only meaningful while its parameters still match what the method's
algorithm.yml currently declares as the tuned value for that run's track (`tuned: {sim: .., invivo: ..,
chisep: ..}`, or a bare scalar = sim). When a tuned value is removed or changed in the yaml — e.g. an
in-vivo tuning that turned out to hurt is deleted — the old run lingers in index.json and the
leaderboard keeps showing a "tuned" variant that no longer corresponds to any declared setting (and can
read as tuned-worse-than-default).

A full re-score naturally omits these (discover_algorithms only expands a tuned variant a method still
declares for its track), so this is a stopgap to keep the published index.json consistent with the
current declarations without re-running every container. Idempotent: re-running it changes nothing once
the index is clean.

  python scripts/prune_stale_tuned.py            # prune results/index.json in place
  python scripts/prune_stale_tuned.py --check    # exit 1 if any stale run exists (no write)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def declared_tuned(slug: str, track: str) -> dict:
    """The {param: value} the method currently declares as tuned for `track` (str values, matching how
    index.json stores run params). Empty if the method/param declares nothing for that track."""
    spec = ROOT / "algorithms" / slug / "algorithm.yml"
    if not spec.exists():
        return {}
    doc = yaml.safe_load(spec.read_text()) or {}
    out = {}
    for p in doc.get("parameters") or []:
        t = p.get("tuned")
        v = t.get(track) if isinstance(t, dict) else (t if track == "sim" else None)
        if v is not None:
            out[str(p["name"])] = str(v)
    return out


def is_stale(run: dict) -> bool:
    """A run is stale iff it's an isolated tuned variant whose params no longer match the declared
    tuned value for its track (including the case where the declaration was removed entirely)."""
    if run.get("mode") != "isolated" or run.get("variant") != "tuned":
        return False
    params = {k: str(v) for k, v in (run.get("params") or {}).items()}
    declared = declared_tuned(run.get("slug", ""), run.get("track", "sim"))
    return not (params and all(declared.get(k) == v for k, v in params.items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, default=ROOT / "results" / "index.json")
    ap.add_argument("--check", action="store_true", help="report stale runs and exit 1; do not write")
    args = ap.parse_args()

    doc = json.loads(args.index.read_text())
    runs = doc.get("runs", [])
    stale = [r for r in runs if is_stale(r)]

    if not stale:
        print("no stale tuned runs — index.json is consistent with the declarations")
        return
    for r in stale:
        print(f"  stale: {r['id']:28} track={r.get('track')} params={r.get('params')}")
    if args.check:
        print(f"{len(stale)} stale tuned run(s)")
        sys.exit(1)

    doc["runs"] = [r for r in runs if not is_stale(r)]
    args.index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"pruned {len(stale)} stale tuned run(s); wrote {args.index} ({len(doc['runs'])} runs)")


if __name__ == "__main__":
    main()
