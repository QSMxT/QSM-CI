#!/usr/bin/env python3
"""Re-apply the runs a rescore changed onto the latest results/index.json, by run id.

score.yml must not `git pull --rebase` its `results/index.json` commit: a rescore can be based on a
commit *before* a prior rescore's results landed, so rebasing conflicts on the same file (that's the
#72 failure — "Pulling is not possible because you have unmerged files"). Instead, at push time we
take the LATEST index.json from main and upsert only the run entries THIS rescore actually changed
(the diff of its own checkout base vs. its scored output, keyed by run id). So concurrent rescores
of different slugs never clobber each other, and a stale base is harmless — a full rescore still
overwrites everything (every id differs), a focused one touches only its slugs.

Existing run order is preserved (changed entries replaced in place; brand-new ids appended).

Usage: merge_index.py BASE SCORED CURRENT OUT
  BASE     index.json this rescore started from (checkout HEAD)
  SCORED   index.json this rescore produced (base + freshly scored runs)
  CURRENT  latest index.json from origin/main
  OUT      where to write the merged result (may equal CURRENT)
"""
import json
import sys


def _runs(path: str) -> list:
    try:
        return json.loads(open(path).read()).get("runs", [])
    except Exception:  # noqa: BLE001 — a missing/empty index is just "no runs"
        return []


def main() -> int:
    base_p, scored_p, current_p, out_p = sys.argv[1:5]
    base = {r["id"]: r for r in _runs(base_p)}
    # Runs this rescore owns = present in its output and new-or-different vs. the base it started from.
    changed = {r["id"]: r for r in _runs(scored_p) if base.get(r["id"]) != r}

    doc = json.loads(open(current_p).read())
    seen, merged = set(), []
    for r in doc.get("runs", []):
        merged.append(changed.get(r["id"], r))
        seen.add(r["id"])
    for rid, r in changed.items():
        if rid not in seen:
            merged.append(r)
    doc["runs"] = merged

    with open(out_p, "w") as f:
        f.write(json.dumps(doc, indent=2) + "\n")
    print(f"re-applied {len(changed)} changed run(s); index now has {len(merged)} runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
