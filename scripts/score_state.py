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

    score_state.py --check-shards --tasks tasks.json [--done-dir .] [--job-conclusions jobs.json]

The merge job's last step: a planned task whose shard artifact never reached merge (neither
`runs-<id>.json` nor `.done`; e.g. it expired before a long serial lent run ended) published nothing
and stays owed (no marker). This makes that loud: `::error::` (exit 1) when its score job succeeded
or its conclusion is unknown — the shard was lost — and `::warning::` when the job was cancelled /
failed / timed out before writing anything.
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
    """Tasks that finished (their `.done` marker), plus the lent-runner jobs the planner settled
    without running them because every row they score is already scored and fresh."""
    return {t["id"] for t in tasks if t.get("settled") or (done_dir / f"runs-{t['id']}.done").exists()}


def missing_shards(tasks: list[dict], done_dir: Path) -> list[str]:
    """Planned tasks (not settled) that handed merge no shard at all: no runs file, no marker."""
    return [t["id"] for t in tasks if not t.get("settled")
            and not (done_dir / f"runs-{t['id']}.json").exists()
            and not (done_dir / f"runs-{t['id']}.done").exists()]


def shard_report(missing: list[str], conclusions: dict[str, str] | None) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the missing shards. A job that succeeded must have uploaded one, so its
    shard was lost (expired, failed upload); with no conclusion to go on, assume lost too."""
    errors, warnings = [], []
    for i in missing:
        c = (conclusions or {}).get(i)
        if c in (None, "success"):
            errors.append(f"shard for {i} missing (job {c or 'conclusion unknown'}; artifact expired or lost "
                          "before merge): not published, still owed")
        else:
            warnings.append(f"no shard for {i} (job {c} before writing any rows): not published, still owed")
    return errors, warnings


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
        # A split task (score_plan.size_focus) `replaces` the coarser ids it was cut from, comma-
        # separated: its method's unsplit focus id, and for a part of a field map's job that job's id
        # too (f-inr-qsm-gt-p1of2 replaces "f-inr-qsm,f-inr-qsm-gt"). Each older entry is paid off once
        # every part this run planned for it finished (or was settled as already fresh); parts of an
        # earlier run that finished are not re-planned (the planner settles them), so parts that
        # complete in separate runs still clear it.
        parts: dict[str, list[str]] = {}
        for t in tasks:
            for r in filter(None, str(t.get("replaces") or "").split(",")):
                parts.setdefault(r, []).append(t["id"])
        replaced = {r for r, ids in parts.items() if all(i in planned_done for i in ids)}
        new_manual = (old_manual - planned_done - replaced) | set(skipped_manual or [])
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
    ap.add_argument("--state", type=Path)
    ap.add_argument("--sha", help="the commit this run scored")
    ap.add_argument("--tasks", type=Path, required=True, help="JSON list of the planned tasks")
    ap.add_argument("--done-dir", type=Path, default=Path("."), help="where the runs-<id>.done markers are")
    ap.add_argument("--skipped-manual", type=Path, default=None,
                    help="JSON list of manual-tier task ids the planner owed but did not schedule")
    ap.add_argument("--check-shards", action="store_true",
                    help="only report planned tasks whose shard never reached merge (exit 1 if one was lost)")
    ap.add_argument("--job-conclusions", type=Path, default=None,
                    help="with --check-shards: JSON {task id: score job conclusion}")
    a = ap.parse_args()
    tasks = json.loads(a.tasks.read_text())
    if a.check_shards:
        conc = None
        if a.job_conclusions and a.job_conclusions.exists():
            try:
                conc = json.loads(a.job_conclusions.read_text())
            except json.JSONDecodeError:
                conc = None
        errors, warnings = shard_report(missing_shards(tasks, a.done_dir), conc)
        for w in warnings:
            print(f"::warning::{w}")
        for e in errors:
            print(f"::error::{e}")
        print(f"shards: {len(errors)} lost, {len(warnings)} never written, of {len(tasks)} planned tasks")
        raise SystemExit(1 if errors else 0)
    if a.state is None or a.sha is None:
        ap.error("--state and --sha are required (unless --check-shards)")
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
