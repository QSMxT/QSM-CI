#!/usr/bin/env python3
"""Drop composed χ-separation rows that run a method off its trained field strength.

A method may declare `field_strength:` in its algorithm.yml (R2PRIMEnet-7T: 7): its trained weights
are only valid at that B0, QSMxT refuses the route anywhere else, and pipeline.py's GRE-only grid
(run_chisep_composed) no longer composes it on a phantom at another field strength. Rows scored
before that rule (e.g. r2primenet-7t~chisep-medi-cmp-meso-3t) would otherwise stay on the
leaderboard forever, since nothing re-scores an id that is no longer planned. This removes them.

score.yml's merge job runs it on every results commit (after merge_index.py, on the latest main), so
the index converges on the rule without a manual step. Idempotent. Each phantom's B0 comes from
scripts/datasets.json `field_strength` (the number pipeline.py plans with); a row whose phantom does
not declare one is kept.

  python scripts/prune_inapplicable.py [results/index.json]          # prune in place
  python scripts/prune_inapplicable.py [results/index.json] --check  # exit 1 if any row would go
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import _field_strength, field_matches, load_datasets  # noqa: E402


def declared_field_strengths(algos_root: Path) -> dict[str, float]:
    """{slug: field_strength} for every method that declares one."""
    out = {}
    for spec in sorted(algos_root.glob("*/algorithm.yml")):
        try:
            doc = yaml.safe_load(spec.read_text())
        except yaml.YAMLError:
            continue
        if isinstance(doc, dict):
            fs = _field_strength(doc, spec.parent.name)
            if fs is not None:
                out[spec.parent.name] = fs
    return out


def inapplicable(row: dict, reg: dict, fields: dict[str, float]) -> "str | None":
    """Why this row should not exist (a composed row with a method off its field strength), or None."""
    combo = row.get("combo")
    if row.get("mode") != "composed" or not isinstance(combo, dict):
        return None
    b0 = reg.get(row.get("phantom"), {}).get("field_strength")
    if b0 is None:
        return None
    for slug in combo.values():
        if not field_matches(fields.get(slug), b0):
            return f"{slug} is trained for {fields[slug]:g} T, phantom {row.get('phantom')} is {b0:g} T"
    return None


def prune(runs: list[dict], reg: dict, fields: dict[str, float]) -> tuple[list[dict], list[tuple[str, str]]]:
    keep, dropped = [], []
    for r in runs:
        why = inapplicable(r, reg, fields)
        if why:
            dropped.append((r.get("id", "?"), why))
        else:
            keep.append(r)
    return keep, dropped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("index", nargs="?", type=Path, default=ROOT / "results" / "index.json")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if any row would be dropped")
    args = ap.parse_args()
    idx = json.loads(args.index.read_text())
    keep, dropped = prune(idx["runs"], load_datasets(), declared_field_strengths(ROOT / "algorithms"))
    for rid, why in dropped:
        print(f"not applicable, dropped: {rid} ({why})")
    print(f"{len(dropped)} row(s) off their method's field strength")
    if args.check:
        sys.exit(1 if dropped else 0)
    if dropped:
        idx["runs"] = keep
        args.index.write_text(json.dumps(idx, indent=2) + "\n")


if __name__ == "__main__":
    main()
