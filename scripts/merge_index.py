#!/usr/bin/env python3
"""Re-apply the runs a rescore changed onto the latest results/index.json, by run id.

score.yml must not `git pull --rebase` its `results/index.json` commit: a rescore can be based on a
commit *before* a prior rescore's results landed, so rebasing conflicts on the same file (that's the
#72 failure — "Pulling is not possible because you have unmerged files"). Instead, at push time we
take the LATEST index.json from main and upsert only the run entries THIS rescore actually changed
(the diff of its own checkout base vs. its scored output, keyed by run id). So concurrent rescores
of different slugs never clobber each other, and a stale base is harmless — a full rescore still
overwrites everything (every id differs), a focused one touches only its slugs.

Score runs OVERLAP (score.yml has no workflow-level concurrency group), so two runs can score the
same id and merge in either order — an older run with a long unrelated task can merge hours after
a newer run already published that id. Every CI-scored row carries `ci_run` ("<run id>.<attempt>",
stamped by pipeline.RunsFile); a changed row is applied only if the row already on main is not
from a NEWER run. Rows without a stamp (legacy, or local runs) are always applied.

Existing run order is preserved (changed entries replaced in place; brand-new ids appended).

Usage: merge_index.py BASE SCORED CURRENT OUT [--superseded-out PATH]
  BASE     index.json this rescore started from (checkout HEAD)
  SCORED   index.json this rescore produced (base + freshly scored runs)
  CURRENT  latest index.json from origin/main
  OUT      where to write the merged result (may equal CURRENT)
  --superseded-out PATH   also write the JSON list of ids NOT applied because main holds a newer row
"""
import json
import sys


def _runs(path: str) -> list:
    try:
        return json.loads(open(path).read()).get("runs", [])
    except Exception:  # noqa: BLE001 — a missing/empty index is just "no runs"
        return []


def run_key(row: dict) -> tuple:
    """Orderable (run id, attempt) from a row's `ci_run`; (0, 0) when unstamped."""
    try:
        rid, _, att = str(row.get("ci_run") or "0.0").partition(".")
        return (int(rid), int(att or 0))
    except ValueError:
        return (0, 0)


def superseded(incoming: dict, current: "dict | None") -> bool:
    """True if `current` (the row already on main) was scored by a NEWER run than `incoming`."""
    return current is not None and run_key(current) > run_key(incoming)


def merge(base: list, scored: list, current: list) -> tuple[list, list]:
    """(merged runs, ids skipped because main already holds a newer row)."""
    base_by = {r["id"]: r for r in base}
    changed = {r["id"]: r for r in scored if base_by.get(r["id"]) != r}
    cur_by = {r["id"]: r for r in current}
    skipped = sorted(i for i, r in changed.items() if superseded(r, cur_by.get(i)))
    for i in skipped:
        del changed[i]
    seen, merged = set(), []
    for r in current:
        merged.append(changed.get(r["id"], r))
        seen.add(r["id"])
    for rid, r in changed.items():
        if rid not in seen:
            merged.append(r)
    return merged, skipped


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base_p, scored_p, current_p, out_p = args[:4]
    sup_out = sys.argv[sys.argv.index("--superseded-out") + 1] if "--superseded-out" in sys.argv else None

    doc = json.loads(open(current_p).read())
    merged, skipped = merge(_runs(base_p), _runs(scored_p), doc.get("runs", []))
    doc["runs"] = merged
    with open(out_p, "w") as f:
        f.write(json.dumps(doc, indent=2) + "\n")
    if sup_out:
        with open(sup_out, "w") as f:
            f.write(json.dumps(skipped) + "\n")
    base_by = {r["id"]: r for r in _runs(base_p)}
    n_changed = len([r for r in _runs(scored_p) if base_by.get(r["id"]) != r and r["id"] not in skipped])
    print(f"re-applied {n_changed} changed run(s); index now has {len(merged)} runs"
          f"{'; NOT applied (a newer run already scored them): ' + ', '.join(skipped) if skipped else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
