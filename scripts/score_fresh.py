"""Which scored rows a re-run would only reproduce ("fresh"), shared by pipeline.py --resume (skip them
inside a job) and score_plan.py (do not schedule a lent-runner part whose every run is fresh).

Kept free of heavy imports: the plan job installs only pyyaml.

A row is fresh when it scored OK in CI at a commit (`ci_sha`) that is an ancestor of `head`, and
nothing it depends on changed since: no RESUME_SCORER_PATHS file and no file under algorithms/<m>/ for
any method m it ran (which pins each method's image, run.sh and parameters). Commits whose message
carries `[skip score]` do not count, exactly as score_plan.changed_files leaves them out of a run's
scope: such a commit declares that it cannot move a number (docs, scheduling, a scorer refactor), so a
row scored before it is as current as one scored after. Anything git cannot answer counts as stale, so
the worst case is re-running a run, never keeping a stale score.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_TOKEN = "[skip score]"
# Paths whose change can move ANY score (the scorer, the stage contract, the container CLI, the
# phantom registry, methods' shared build files). A row scored before such a change is not reused.
RESUME_SCORER_PATHS = ("eval/", "qsm_ci/", "stages.yml", "scripts/pipeline.py", "scripts/scoring.py",
                       "scripts/publish_volumes.py", "scripts/datasets.json", "algorithms/_")


def git_changed(base: str, head: str, cwd: Path = ROOT) -> "set[str] | None":
    """Files changed by the first-parent commits in base..head, leaving out `[skip score]` commits;
    None when git cannot tell (base not an ancestor of head, or not in history)."""
    try:
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=cwd,
                          capture_output=True, timeout=60).returncode != 0:
            return None
        r = subprocess.run(["git", "log", "--first-parent", "--diff-merges=first-parent", "--name-only",
                            "--format=%x1e%H%x1f%B%x1f", f"{base}..{head}"],
                           cwd=cwd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode:
        return None
    files: set[str] = set()
    for rec in r.stdout.split("\x1e")[1:]:
        _sha, body, names = (rec.split("\x1f") + ["", ""])[:3]
        if SKIP_TOKEN in body:
            continue
        files |= set(names.split())
    return files


def row_members(row: dict) -> set:
    """Every method a row ran: a composed row's combo stages and its slug's parts (a span row's combo
    names only its field map), an isolated row's slug; without the ground-truth "gt" start."""
    combo = row.get("combo") or {}
    return ({str(v) for v in combo.values() if v} | set(str(row.get("slug") or "").split("+"))) - {"gt", ""}


def fresh_ids(rows: list, head: str = "HEAD", changed=git_changed, modes=("composed",)) -> frozenset:
    """Ids of the rows (of the given `mode`s) that re-running would only reproduce (module docstring)."""
    by_sha: dict = {}
    for r in rows:
        if r.get("mode") in modes and r.get("status") == "ok" and r.get("ci_sha") and r.get("id"):
            by_sha.setdefault(r["ci_sha"], []).append(r)
    fresh = set()
    for sha, rs in by_sha.items():
        files = changed(sha, head)
        if files is None or any(f.startswith(RESUME_SCORER_PATHS) for f in files):
            continue
        touched = {f.split("/")[1] for f in files if f.startswith("algorithms/") and f.count("/") >= 2}
        fresh |= {r["id"] for r in rs if not (row_members(r) & touched)}
    return frozenset(fresh)
