#!/usr/bin/env python3
"""One-off: namespace the retired χ-sep default phantom's run ids before meso-3t takes them over.

A track's default phantom keeps bare run ids (`<slug>-iso`); every other phantom appends
`-<phantom>` (pipeline.phantom_suffix). chisep-mc was the chisep default, so its rows in
results/index.json hold the bare ids. With meso-3t the default, its first re-score would overwrite
them in place and chisep-mc's results would be lost. Run this ONCE, on the branch that makes
meso-3t the default, before that re-score: every row stamped `phantom: chisep-mc` whose id has no
`-chisep-mc` suffix gets it (and its results/<id>/ dir, if any, is renamed to match). Idempotent.

Usage: python scripts/oneoff/rekey_retired_chisep_default.py [--phantom chisep-mc] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rekey(index: dict, phantom: str) -> dict:
    """{old id: new id} for the phantom's bare-id rows; rewrites `index` in place."""
    moved = {}
    sfx = f"-{phantom}"
    for r in index["runs"]:
        if r.get("phantom") == phantom and not r["id"].endswith(sfx):
            moved[r["id"]] = r["id"] + sfx
            r["id"] += sfx
    return moved


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phantom", default="chisep-mc")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    f = a.results / "index.json"
    index = json.loads(f.read_text())
    moved = rekey(index, a.phantom)
    for old, new in moved.items():
        print(f"{old} -> {new}")
        if not a.dry_run and (a.results / old).is_dir():
            (a.results / old).rename(a.results / new)
    if not a.dry_run and moved:
        f.write_text(json.dumps(index, indent=2) + "\n")
    print(f"{len(moved)} run(s) {'would be ' if a.dry_run else ''}re-keyed")


if __name__ == "__main__":
    main()
