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
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import _tuned_overrides  # noqa: E402  — the canonical tuned-value resolver


def declared_tuned(slug: str, dataset: str, phantom: "str | None") -> "dict | None":
    """What the method currently declares as tuned here, or None when that cannot be determined.

    Resolution is delegated to pipeline._tuned_overrides — the same function that decides which tuned
    variant gets created in the first place. This module used to reimplement it and had drifted: it
    looked the value up by TRACK only, while `tuned:` may also be keyed by a specific PHANTOM
    (`tuned: {chisep: 0.6, ridani-3t-iso: 0.8, ridani-3t-aniso: 0.9}`). Every per-phantom tuned run
    therefore compared against a declaration that did not exist and was reported stale: on the
    2026-09 index that was 4 of 4 tuned r2prime-scaled-qsmci runs, all of which match their
    phantom's declared value exactly. Deleting rows a re-score would immediately recreate is the
    opposite of this script's purpose, so the lookup has to be the canonical one, not a copy of it.

    None (cannot tell) is deliberately distinct from {} (nothing declared). A missing algorithm.yml
    means the checkout cannot answer the question, not that the tuning was withdrawn.
    """
    spec = ROOT / "algorithms" / slug / "algorithm.yml"
    if not spec.exists():
        return None
    doc = yaml.safe_load(spec.read_text()) or {}
    return _tuned_overrides(doc, dataset, phantom)


def is_stale(run: dict) -> bool:
    """A run is stale iff it's an isolated tuned variant whose params no longer match the declared
    tuned value for its dataset and phantom (including the case where the declaration was removed).

    `domain` is preferred over `track` for the dataset key: chi-separation rows are stamped
    `track: sim` while carrying `domain: chisep`, so keying on track alone looks up the wrong family
    and finds nothing declared."""
    if run.get("mode") != "isolated" or run.get("variant") != "tuned":
        return False
    dataset = run.get("domain") or run.get("track") or "sim"
    declared = declared_tuned(run.get("slug", ""), dataset, run.get("phantom"))
    if declared is None:
        return False                      # cannot judge from this checkout — never delete on a guess
    params = {k: str(v) for k, v in (run.get("params") or {}).items()}
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
