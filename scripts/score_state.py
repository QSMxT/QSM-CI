#!/usr/bin/env python3
"""Record what a score run finished — results/scoring-state.json — so the next run knows what is
still owed. The merge job of score.yml runs this inside its commit-retry loop, on the latest main.

    score_state.py --state results/scoring-state.json --sha <run's commit> --tasks tasks.json [--done-dir .]

A task is DONE iff its `runs-<id>.done` marker exists in --done-dir (pipeline.py writes it after
the runs file is final; the score job uploads both with `if: always()`, so a cancelled, timed-out
or failed job hands merge its partial rows but NO marker). Everything else the run planned becomes
pending: a shard task → `pending_full` (a shard is a slice of the whole hosted matrix), a focus /
in-vivo task → its slug in `pending_slugs`. The planner (score_plan.py) folds pending work into the
next run's scope, so no planned work is ever silently lost.

Merging with the existing state (two runs can publish in either order):
  - if the run's commit descends from the recorded `scored_sha` (the normal case: this run is the
    newest to publish), it advances `scored_sha`, clears the pending entries it completed, and
    adds its own unfinished ones;
  - otherwise (a newer run already published), `scored_sha` stays and this run only ADDS its
    unfinished work — its completed tasks were scored at an older commit and may be stale, so they
    must not clear anything.
Either way the invariant holds: every change not yet scored is in `scored_sha..main` or in pending.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def done_ids(tasks: list[dict], done_dir: Path) -> set[str]:
    return {t["id"] for t in tasks if (done_dir / f"runs-{t['id']}.done").exists()}


def unfinished(tasks: list[dict], done: set[str]) -> tuple[bool, set[str]]:
    """(pending_full, pending_slugs) for the tasks that did not finish. manual-include recovery
    tasks are one-off and never carried."""
    full, slugs = False, set()
    for t in tasks:
        if t["id"] in done or t.get("id") == "manual-include":
            continue
        if "shard" in t:
            full = True
        elif t.get("focus"):
            slugs.add(t["focus"])
    return full, slugs


def completed_slugs(tasks: list[dict], done: set[str]) -> set[str]:
    return {t["focus"] for t in tasks if t["id"] in done and t.get("focus")}


def update(cur: dict, sha: str, tasks: list[dict], done: set[str], ancestor=is_ancestor,
           now: str | None = None, skipped_manual: list[str] | None = None) -> dict:
    """Pure state transition (see module docstring). `skipped_manual` = task ids the planner owed
    but was not allowed to schedule (manual tier / manual phantom): they are remembered in
    `pending_manual` until a run that IS allowed to schedule them (include_manual, or the slug named
    on dispatch) finishes them — `scored_sha` advancing must not make them look scored."""
    p_full, p_slugs = unfinished(tasks, done)
    old_sha = cur.get("scored_sha") or ""
    old_full = bool(cur.get("pending_full"))
    old_slugs = set(cur.get("pending_slugs") or [])
    old_manual = set(cur.get("pending_manual") or [])
    ran_full = any("shard" in t for t in tasks)
    planned_done = done & {t["id"] for t in tasks}
    if not old_sha or ancestor(old_sha, sha):
        new_sha = sha
        # A complete shard sweep re-scores the whole hosted matrix, which is what pending_full owed.
        new_full = p_full or (old_full and not ran_full)
        new_slugs = (old_slugs - completed_slugs(tasks, done)) | p_slugs
        # A full run whose shards all finished also covered every hosted-tier pending slug; the
        # dedicated ones ran as their own focus tasks and are settled per task above.
        if ran_full and not p_full:
            new_slugs -= {s for s in old_slugs if not any(t.get("focus") == s for t in tasks)}
        new_manual = (old_manual - planned_done) | set(skipped_manual or [])
    else:
        new_sha = old_sha
        new_full = old_full or p_full
        new_slugs = old_slugs | p_slugs
        new_manual = old_manual | set(skipped_manual or [])   # never clear from a stale commit
    return {"scored_sha": new_sha, "pending_full": new_full, "pending_slugs": sorted(new_slugs),
            "pending_manual": sorted(new_manual),
            "updated": now or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "last_run": {"sha": sha, "planned": len(tasks), "done": len(planned_done)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--sha", required=True, help="the commit this run scored")
    ap.add_argument("--tasks", type=Path, required=True, help="JSON list of the planned tasks")
    ap.add_argument("--done-dir", type=Path, default=Path("."), help="where the runs-<id>.done markers are")
    ap.add_argument("--skipped-manual", type=Path, default=None,
                    help="JSON list of manual-tier task ids the planner owed but did not schedule")
    a = ap.parse_args()
    tasks = json.loads(a.tasks.read_text())
    try:
        cur = json.loads(a.state.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cur = {}
    done = done_ids(tasks, a.done_dir)
    skipped = json.loads(a.skipped_manual.read_text()) if a.skipped_manual and a.skipped_manual.exists() else []
    new = update(cur if isinstance(cur, dict) else {}, a.sha, tasks, done, skipped_manual=skipped)
    a.state.parent.mkdir(parents=True, exist_ok=True)
    a.state.write_text(json.dumps(new, indent=2) + "\n")
    missing = [t["id"] for t in tasks if t["id"] not in done]
    print(f"scoring-state: scored_sha={new['scored_sha'][:12]} pending_full={new['pending_full']} "
          f"pending_slugs={new['pending_slugs']} pending_manual={new['pending_manual']} "
          f"({len(done)}/{len(tasks)} tasks finished"
          f"{'; unfinished: ' + ', '.join(missing) if missing else ''})")


if __name__ == "__main__":
    main()
