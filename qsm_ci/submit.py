"""`qsm-ci submit` — open a pull request adding your submission folder.

Uses the GitHub CLI (`gh`) when available: commit the folder on a branch and open a PR draft in
the browser. If you're not in a clone of QSM-CI, it prints the fork+clone steps instead of guessing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

UPSTREAM = "QSMxT/QSM-CI"


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _git(*args, **kw):
    return subprocess.run(["git", *args], **kw)


def _in_repo() -> bool:
    return _git("rev-parse", "--is-inside-work-tree", capture_output=True).returncode == 0


def run_submit(args) -> int:
    slug = args.slug
    algo = Path("algorithms") / slug
    if not (algo / "algorithm.yml").exists():
        print(f"! no algorithms/{slug}/algorithm.yml here.")
        print(f"  Run this from a clone of {UPSTREAM} with your folder under algorithms/.")
        return 1

    if not _has("git"):
        print("! git not found — install git to submit.")
        return 1
    if not _in_repo():
        print("This folder isn't a git checkout of QSM-CI. To submit:\n")
        print(f"  gh repo fork {UPSTREAM} --clone   # or fork on github.com and clone")
        print(f"  cp -r algorithms/{slug} <clone>/algorithms/{slug}")
        print(f"  cd <clone> && qsm-ci submit {slug}")
        return 1

    branch = f"submit/{slug}"
    print(f"▸ committing algorithms/{slug} on branch {branch}")
    _git("checkout", "-b", branch)
    _git("add", str(algo))
    _git("commit", "-m", f"Add {slug} submission")

    if _has("gh"):
        print("▸ pushing and opening a PR draft (gh)")
        _git("push", "-u", "origin", branch)
        # --web opens the PR form in the browser; nothing is submitted without your click.
        subprocess.run(["gh", "pr", "create", "--web", "--title", f"Add {slug}",
                        "--body", f"Adds the `{slug}` QSM-CI submission."])
    else:
        print("\nCommitted. Push and open a PR:")
        print(f"  git push -u origin {branch}")
        print(f"  # then open a PR against {UPSTREAM} on github.com")
    return 0
