"""`qsm-ci submit` — open a pull request adding your submission folder.

Interactive and fork-aware: it walks you through each step (branch, commit, push, PR) and, when your
`origin` is the upstream you can't push to, offers to use a fork you already have, create one under
your GitHub account with `gh`, or push directly if you're a maintainer. Nothing is pushed or opened
without your confirmation.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

UPSTREAM = "QSMxT/QSM-CI"


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _git(*args, **kw):
    return subprocess.run(["git", *args], **kw)


def _in_repo() -> bool:
    return _git("rev-parse", "--is-inside-work-tree", capture_output=True).returncode == 0


def _remote_url(remote: str) -> "str | None":
    r = _git("remote", "get-url", remote, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _owner_repo(url: "str | None") -> "str | None":
    if not url:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _confirm(question: str, default: bool = True) -> bool:
    if not _interactive():
        return default
    ans = input(f"{question}{' [Y/n] ' if default else ' [y/N] '}").strip().lower()
    return default if not ans else ans.startswith("y")


def _ask(question: str) -> str:
    return input(question).strip()


def _setup_fork(head_hint: "str | None") -> "tuple[str | None, str | None]":
    """Decide where to push (a fork) and whose branch the PR head is. Returns (remote, owner)."""
    print(f"  Your 'origin' is the upstream ({UPSTREAM}), which you probably can't push to.")
    print("  Submitting a PR needs a fork.\n")
    if not _interactive():
        print("  Re-run in a terminal to set one up, or do it yourself:")
        print(f"    gh repo fork {UPSTREAM} --clone   # then run  qsm-ci submit  from that clone")
        return None, None
    print("  How would you like to proceed?")
    print("    [1] I already have a fork — I'll paste its URL")
    print("    [2] Create a fork now under my GitHub account (uses gh)")
    print("    [3] I have push access to the upstream — push there directly")
    print("    [4] Cancel")
    choice = _ask("  > ")

    if choice == "1":
        url = _ask("  Fork URL (e.g. https://github.com/you/QSM-CI): ")
        owner = _owner_repo(url)
        if not owner:
            print("  ✗ couldn't parse an owner/repo from that URL.")
            return None, None
        _git("remote", "remove", "fork", capture_output=True)
        if _git("remote", "add", "fork", url).returncode != 0:
            print("  ✗ couldn't add the 'fork' remote.")
            return None, None
        print(f"  added remote 'fork' → {owner}")
        return "fork", owner.split("/")[0]

    if choice == "2":
        if not _has("gh"):
            print("  ✗ gh (GitHub CLI) isn't installed — needed to create a fork. Install it, or use option 1.")
            return None, None
        print(f"  creating your fork of {UPSTREAM} …")
        r = subprocess.run(["gh", "repo", "fork", UPSTREAM, "--remote", "--remote-name", "fork", "--clone=false"])
        if r.returncode != 0:
            print("  ✗ fork creation failed.")
            return None, None
        owner = _owner_repo(_remote_url("fork"))
        return "fork", (owner.split("/")[0] if owner else head_hint)

    if choice == "3":
        return "origin", UPSTREAM.split("/", 1)[0]

    return None, None  # cancel / anything else


def run_submit(args) -> int:
    slug = args.slug
    algo = Path("algorithms") / slug
    if not (algo / "algorithm.yml").exists():
        print(f"! no algorithms/{slug}/algorithm.yml here.")
        print(f"  Run this from a clone of {UPSTREAM} (or your fork) with your folder under algorithms/.")
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

    print(f"▸ Submitting '{slug}' to {UPSTREAM}.\n")

    origin = _owner_repo(_remote_url("origin"))
    if origin and origin.lower() != UPSTREAM.lower():
        # origin is already a fork (or some other pushable remote)
        push_remote, head_owner = "origin", origin.split("/")[0]
        print(f"  'origin' is {origin} — I'll push your branch there and open a PR to {UPSTREAM}.")
        if not _confirm("  Proceed?"):
            return 1
    else:
        push_remote, head_owner = _setup_fork(origin.split("/")[0] if origin else None)
        if push_remote is None:
            print("  Cancelled.")
            return 1

    branch = f"submit/{slug}"
    if not _confirm(f"  Create branch '{branch}' and commit algorithms/{slug}?"):
        return 1
    if _git("rev-parse", "--verify", branch, capture_output=True).returncode == 0:
        print(f"  branch '{branch}' exists — checking it out.")
        _git("checkout", branch)
    else:
        _git("checkout", "-b", branch)
    _git("add", str(algo))
    if _git("commit", "-m", f"Add {slug} submission", capture_output=True).returncode != 0:
        print("  (nothing new to commit — the folder is already committed on this branch)")

    if not _confirm(f"  Push '{branch}' to '{push_remote}'?"):
        print(f"  Skipped. Push later with:  git push -u {push_remote} {branch}")
        return 0
    if _git("push", "-u", push_remote, branch).returncode != 0:
        print(f"! push to '{push_remote}' failed (no access to that remote?). "
              f"Fix the remote and retry, or push manually.")
        return 1

    if _has("gh"):
        if _confirm("  Open the pull request now (in your browser)?"):
            print("  opening a PR draft — nothing is submitted until you click Create.")
            subprocess.run(["gh", "pr", "create", "--repo", UPSTREAM, "--head", f"{head_owner}:{branch}",
                            "--web", "--title", f"Add {slug}",
                            "--body", f"Adds the `{slug}` QSM-CI submission."])
    else:
        print(f"\n  Committed + pushed. Open a PR from  {head_owner}:{branch}  into  {UPSTREAM}:main")
    return 0
