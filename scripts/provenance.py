#!/usr/bin/env python3
"""When a row of results/index.json was scored (`scored_at`) and which version of each method it ran
(`method_versions`). The submission page shows both: the date under the metrics, and per method the
Zenodo release that first shipped that code (or the commit, if it isn't released yet).

pipeline.RunsFile.stamp records both on every CI-scored row. Run as a script, this fills them in on
rows scored before that existed (`scored_at` = the start of the row's GitHub Actions run `ci_run`,
via the gh CLI; `method_versions` from git at the row's `ci_sha`). score.yml's merge job runs it on
every publish, on top of the latest main, so it never conflicts with concurrent results commits.
Idempotent: a row that already has a field keeps it, so once everything is filled it does nothing.
Rows with no `ci_run` (scored locally, long ago) are left alone.

Standard library only: the merge job doesn't install the qsm-ci package.

  python scripts/provenance.py [results/index.json]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY") or "QSMxT/QSM-CI"

_METHOD_COMMITS: dict = {}


def method_commit(slug: str, sha: str | None) -> dict | None:
    """The version of method `slug` a CI run scored: the last commit touching algorithms/<slug>/ at
    `sha` (the scored commit), as {"commit", "date"} (committer date, UTC ISO). The website maps it
    to the Zenodo release that first shipped that code (registry.json `updated_at`), or shows it as
    unreleased. None when git can't answer: no such method dir, not a checkout, or a shallow clone
    whose history doesn't reach the commit (score.yml checks out full history for this)."""
    key = (slug, sha)
    if key not in _METHOD_COMMITS:
        out = None
        if (ROOT / "algorithms" / slug).is_dir():
            try:
                res = subprocess.run(["git", "log", "-1", "--format=%H%x09%cI", sha or "HEAD", "--",
                                      f"algorithms/{slug}"], cwd=ROOT, capture_output=True, text=True,
                                     timeout=30)
                commit, _, date = res.stdout.strip().partition("\t")
                if res.returncode == 0 and commit and date:
                    out = {"commit": commit, "date": date}
            except (OSError, subprocess.SubprocessError):
                pass
        _METHOD_COMMITS[key] = out
    return _METHOD_COMMITS[key]


def row_methods(row: dict) -> list[str]:
    """The method slugs a row ran, in pipeline order: its combo (minus the ground-truth "gt" field
    start) or, for an isolated / χ-separation row, the "+"-joined slug."""
    combo = row.get("combo") or {}
    steps = [combo[k] for k in ("field_mapping", "bfr", "dipole") if combo.get(k)] or \
        str(row.get("slug") or "").split("+")
    return [s for s in dict.fromkeys(steps) if s and s != "gt"]


def run_started(run_id: str) -> str | None:
    """When GitHub Actions run `run_id` started (UTC ISO), or None if gh can't say."""
    try:
        res = subprocess.run(["gh", "api", f"repos/{REPO}/actions/runs/{run_id}", "--jq", ".run_started_at"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return (res.stdout.strip() or None) if res.returncode == 0 else None


def backfill(doc: dict) -> tuple[int, int]:
    """Fill `scored_at` / `method_versions` in place; returns how many rows got each."""
    started: dict[str, str | None] = {}
    n_date = n_ver = 0
    for row in doc.get("runs", []):
        if not row.get("ci_run"):
            continue
        if "scored_at" not in row:
            rid = str(row["ci_run"]).partition(".")[0]
            if rid not in started:
                started[rid] = run_started(rid)
            if started[rid]:
                row["scored_at"] = started[rid]
                n_date += 1
        if "method_versions" not in row and row.get("ci_sha"):
            versions = {s: v for s in row_methods(row) if (v := method_commit(s, row["ci_sha"]))}
            if versions:
                row["method_versions"] = versions
                n_ver += 1
    return n_date, n_ver


def main(argv: list[str]) -> None:
    index = Path(argv[0]) if argv else ROOT / "results" / "index.json"
    doc = json.loads(index.read_text())
    n_date, n_ver = backfill(doc)
    if n_date or n_ver:
        index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"provenance backfill: scored_at on {n_date} rows, method_versions on {n_ver} rows")


if __name__ == "__main__":
    main(sys.argv[1:])
