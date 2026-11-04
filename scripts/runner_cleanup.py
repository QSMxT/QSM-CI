#!/usr/bin/env python3
"""Free disk on a QSM-CI self-hosted runner box: stale container images, scratch dirs, old logs.

Run by .github/workflows/runner-cleanup.yml (weekly + on dispatch) on the self-hosted runners. Nothing
else in QSM-CI prunes them, and on 2026-11-04 the box's /storage filled up ("No space left on
device" in the runner's own _diag), which killed jobs. Safe while other jobs run:

  - container images: only QSM-CI's own (ghcr.io/astewartau/qsm-ci/*, and the per-run
    `qsmxt-under-test:<run id>` images parity.yml builds), only via `docker rmi` WITHOUT -f, so
    docker itself refuses any image a container (running or stopped) still uses; such images are
    skipped up front as well. Docker records no last-used time, so "not used in the last N days"
    means: no container uses it, it was not pulled/built/tagged in the last N days (LastTagTime, or
    Created when never tagged), and, unless --drop-pinned, current main does not pin it (the next
    scoring/evaluate job would only pull it again). A `qsmxt-under-test:<run id>` image goes as soon
    as its parity run has finished (it is never used again).
  - scratch dirs: `.work/` (pipeline.py) and `.parity/` (parity.py) in each repo checkout under each
    runner's `_work/`, only when NOTHING inside changed in the last 2 days (a running job writes
    there). This job's own workspace is never touched (actions/checkout already cleans it).
    Sibling runner directories next to this one are cleaned too, but only QSM-CI's own: the box is
    shared with other projects' runners (Neurodesk's), so a sibling counts only when its `.runner`
    file registers it to QSMxT/QSM-CI.
  - `_diag` logs (`*.log`, `pages/*`) older than 7 days, for the same runners.
  - `qsm-ci-*` directories in the system temp dir (`qsm-ci run`'s per-run TemporaryDirectory with a
    copy of every input and output volume, and the Zenodo fetch's mkdtemp) idle for 2 days: a job
    killed at its cap or cancelled never runs the cleanup, so each kill leaks one.
  - Docker is NOT the only consumer of the box's disk (on 2026-11-04 images were 179 GB of a full
    974 GB /storage), so the job also prints where the rest is: each runner's `_work/` entries,
    `~/.cache/*`, the temp dir and Docker's root, by size. What it cannot safely delete (a
    previous job's checkout leftovers: data/<phantom> datasets, .osfcache zips, results/ volumes,
    which the next checkout on that runner removes) is reported, not removed.
  - stopped `qsmci`-labelled containers older than 7 days. Nothing global: the Docker daemon is
    shared with other projects' runners, so no `image prune` (dangling) or `builder prune`, whose
    filters cannot tell QSM-CI's from theirs.

  python scripts/runner_cleanup.py [--dry-run] [--image-days 7] [--scratch-days 2] [--diag-days 7]
                                   [--drop-pinned]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QSMCI_PREFIX = "ghcr.io/astewartau/qsm-ci/"
UNDER_TEST = "qsmxt-under-test"          # parity.yml: qsmxt-under-test:<run id>[-models]
SCRATCH = (".work", ".parity")
DAY = 86400.0


# ---------------------------------------------------------------------------------------------- images

def pinned_refs(algos: Path) -> set[str]:
    """Every `image:` reference current main pins (algorithms/*/algorithm.yml), comment stripped."""
    out = set()
    for spec in algos.glob("*/algorithm.yml"):
        for m in re.finditer(r"^image:\s*(\S+)", spec.read_text(), re.M):
            out.add(m.group(1).strip("\"'"))
    return out


def _refs(img: dict) -> list[str]:
    return [r for r in (img.get("RepoTags") or []) if r and not r.startswith("<none>")] \
        + [r for r in (img.get("RepoDigests") or []) if r and not r.startswith("<none>")]


def _ts(s: "str | None") -> "float | None":
    """Docker's RFC 3339 (nanosecond) timestamp → epoch seconds; None for the zero time / missing."""
    if not s or s.startswith("0001-01-01"):
        return None
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)?", s)
    if not m:
        return None
    tz = m.group(2) or "Z"
    return dt.datetime.fromisoformat(m.group(1) + ("+00:00" if tz == "Z" else tz)).timestamp()


def under_test_run(ref: str) -> "str | None":
    m = re.fullmatch(UNDER_TEST + r":(\d+)(?:-models)?", ref)
    return m.group(1) if m else None


def image_verdict(img: dict, *, in_use: set[str], pinned: set[str], now: float, days: float,
                  drop_pinned: bool, run_finished) -> "tuple[bool, str]":
    """(remove?, why) for one `docker image inspect` record. `run_finished(run_id)` → True / False /
    None (unknown, e.g. no API access: kept)."""
    refs = _refs(img)
    ours = [r for r in refs if r.startswith(QSMCI_PREFIX) or r.split(":")[0] == UNDER_TEST]
    if not ours:
        return False, "not a QSM-CI image"
    if img.get("Id") in in_use:
        return False, "used by a container"
    last = _ts((img.get("Metadata") or {}).get("LastTagTime")) or _ts(img.get("Created")) or now
    age = (now - last) / DAY
    runs = {under_test_run(r) for r in ours} - {None}
    if runs:
        if all(run_finished(r) is True for r in sorted(runs)):
            return True, f"parity build of finished run {', '.join(sorted(runs))}"
        if age > days:
            return True, f"parity build, {age:.1f} d old"
        return False, "parity build of a run still in progress (or unknown)"
    if not drop_pinned and any(r in pinned for r in ours):
        return False, "pinned on main"
    if age <= days:
        return False, f"pulled/tagged {age:.1f} d ago"
    return True, f"unpinned, last pulled/tagged {age:.1f} d ago"


# ---------------------------------------------------------------------------------------- directories

def registered_to(runner_dir: Path) -> str:
    """The repository a runner directory's `.runner` file registers it to ("" when unreadable)."""
    try:
        cfg = json.loads((runner_dir / ".runner").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    return str(cfg.get("gitHubUrl", "")).rstrip("/")


def runner_roots(own_root: Path) -> list[Path]:
    """This runner's directory and any sibling QSM-CI runner directory beside it (same box). Other
    projects' runners on a shared box are never included."""
    roots = [own_root]
    mine = registered_to(own_root)
    try:
        for d in sorted(own_root.parent.iterdir()):
            if (d != own_root and d.is_dir() and (d / "_work").is_dir() and mine
                    and registered_to(d) == mine):
                roots.append(d)
    except OSError:
        pass
    return roots


def newest_mtime(path: Path) -> float:
    """Latest mtime of anything under `path` (itself included); unreadable entries count as now."""
    newest = 0.0
    try:
        newest = path.lstat().st_mtime
    except OSError:
        return time.time()
    for dirpath, dirnames, filenames in os.walk(path, onerror=lambda e: None):
        for n in dirnames + filenames:
            try:
                newest = max(newest, os.lstat(os.path.join(dirpath, n)).st_mtime)
            except OSError:
                return time.time()
    return newest


def stale_scratch(roots: list[Path], own_workspace: "Path | None", now: float, days: float) -> list[Path]:
    """`.work/` / `.parity/` in each repo checkout (_work/<repo>/<repo>/) with nothing newer than `days`."""
    out = []
    own = own_workspace.resolve() if own_workspace else None
    for root in roots:
        for checkout in sorted((root / "_work").glob("*/*")):
            if not checkout.is_dir() or checkout.name.startswith("_") or checkout.parent.name.startswith("_"):
                continue
            if own is not None and checkout.resolve() == own:
                continue                     # this job's own workspace
            for name in SCRATCH:
                d = checkout / name
                if d.is_dir() and not d.is_symlink() and (now - newest_mtime(d)) / DAY > days:
                    out.append(d)
    return out


def stale_tmp(tmp: Path, now: float, days: float) -> list[Path]:
    """`qsm-ci-*` dirs in the temp dir (qsm-ci run / Zenodo fetch scratch) with nothing newer than `days`."""
    out = []
    try:
        for d in sorted(tmp.glob("qsm-ci-*")):
            if d.is_dir() and not d.is_symlink() and (now - newest_mtime(d)) / DAY > days:
                out.append(d)
    except OSError:
        pass
    return out


def old_diag(roots: list[Path], now: float, days: float) -> list[Path]:
    out = []
    for root in roots:
        diag = root / "_diag"
        for f in sorted(list(diag.glob("*.log")) + list(diag.glob("pages/*"))):
            try:
                if f.is_file() and (now - f.stat().st_mtime) / DAY > days:
                    out.append(f)
            except OSError:
                continue
    return out


# --------------------------------------------------------------------------------------------- runtime

def sh(*args: str, check: bool = False) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def run_finished_api(repo: str, token: str):
    cache: dict[str, "bool | None"] = {}

    def finished(run_id: str) -> "bool | None":
        if run_id not in cache:
            try:
                req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
                                             headers={"Authorization": "Bearer " + token,
                                                      "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    cache[run_id] = json.load(r).get("status") == "completed"
            except urllib.error.HTTPError as e:
                cache[run_id] = True if e.code == 404 else None
            except Exception:  # noqa: BLE001 — unknown: keep the image
                cache[run_id] = None
        return cache[run_id]
    return finished


def clean_images(args, now: float) -> None:
    if not shutil.which("docker"):
        print("docker: not installed, nothing to do")
        return
    if subprocess.run(["docker", "info"], capture_output=True).returncode:
        print("::warning::docker is installed but its daemon is unreachable from this job; images not cleaned")
        return
    def prune(*cmd):
        print("$ docker " + " ".join(cmd))
        if not args.dry_run:
            print(sh("docker", *cmd).strip() or "(nothing)")
    # Stopped QSM-CI containers only (`container prune` never touches a running one); frees their images.
    prune("container", "prune", "-f", "--filter", "label=qsmci", "--filter", f"until={int(args.image_days * 24)}h")
    # Image ids (sha256:…, as `docker image inspect` prints Id) of every container, running or stopped.
    cids = sh("docker", "ps", "-aq", "--no-trunc").split()
    in_use = set(sh("docker", "inspect", "--format", "{{.Image}}", *cids).split()) if cids else set()
    ids = sh("docker", "images", "-q", "--no-trunc").split()
    imgs = json.loads(sh("docker", "image", "inspect", *sorted(set(ids))) or "[]") if ids else []
    pinned = pinned_refs(ROOT / "algorithms")
    finished = run_finished_api(os.environ.get("REPO", ""), os.environ.get("GH_TOKEN", "")) \
        if os.environ.get("GH_TOKEN") and os.environ.get("REPO") else (lambda _r: None)
    removed = 0
    for img in imgs:
        rm, why = image_verdict(img, in_use=in_use, pinned=pinned, now=now, days=args.image_days,
                                drop_pinned=args.drop_pinned, run_finished=finished)
        refs = _refs(img)
        if not rm:
            if refs and any(r.startswith(QSMCI_PREFIX) or r.startswith(UNDER_TEST) for r in refs):
                print(f"keep   {refs[0]}  ({why})")
            continue
        print(f"remove {refs[0]}  ({why})")
        removed += 1
        if not args.dry_run:
            # No -f: docker refuses an image any container still uses, even one started since we looked.
            r = subprocess.run(["docker", "rmi", *refs], capture_output=True, text=True)
            if r.returncode:
                print(f"  kept by docker: {r.stderr.strip()}")
    print(f"{removed} QSM-CI image(s) {'would be ' if args.dry_run else ''}removed")
    # No `image prune` / `builder prune`: the daemon is shared with other projects' runners.


def clean_paths(args, now: float) -> None:
    ws = os.environ.get("RUNNER_WORKSPACE")      # <runner root>/_work/<repo>
    if not ws:
        print("RUNNER_WORKSPACE unset (not on a runner): skipping scratch dirs and _diag")
        return
    own_root = Path(ws).resolve().parent.parent
    roots = runner_roots(own_root)
    print("runner directories: " + ", ".join(str(r) for r in roots))
    own_ws = Path(os.environ["GITHUB_WORKSPACE"]) if os.environ.get("GITHUB_WORKSPACE") else None
    for d in stale_scratch(roots, own_ws, now, args.scratch_days):
        print(f"remove {d}/ (nothing changed for > {args.scratch_days:g} d)")
        if not args.dry_run:
            shutil.rmtree(d, ignore_errors=True)
    logs = old_diag(roots, now, args.diag_days)
    print(f"remove {len(logs)} _diag log(s) older than {args.diag_days:g} d")
    for f in logs:
        if not args.dry_run:
            try:
                f.unlink()
            except OSError as e:
                print(f"  could not remove {f}: {e}")


def clean_tmp(args, now: float) -> None:
    import tempfile
    tmp = Path(tempfile.gettempdir())
    for d in stale_tmp(tmp, now, args.scratch_days):
        print(f"remove {d}/ (qsm-ci run scratch, nothing changed for > {args.scratch_days:g} d)")
        if not args.dry_run:
            shutil.rmtree(d, ignore_errors=True)
            if d.exists():
                print(f"  could not fully remove {d} (files owned by another user, e.g. a container's root?)")


def report_usage() -> None:
    """Where the disk goes besides Docker images — printed largest first, nothing removed."""
    import tempfile
    places = []
    ws = os.environ.get("RUNNER_WORKSPACE")
    if ws:
        for root in runner_roots(Path(ws).resolve().parent.parent):
            places += sorted((root / "_work").glob("*")) + sorted((root / "_work").glob("*/*"))
            places.append(root / "_diag")
    places += sorted((Path.home() / ".cache").glob("*")) + [Path(tempfile.gettempdir())]
    if shutil.which("docker"):
        droot = sh("docker", "info", "--format", "{{.DockerRootDir}}").strip()
        if droot:
            places.append(Path(droot))
    sizes = []
    for pth in dict.fromkeys(places):
        if pth.is_dir():
            out = sh("du", "-sxk", str(pth)).split("\t")[0]
            if out.strip().isdigit():
                sizes.append((int(out), pth))
    print("largest directories (not removed unless listed above):")
    for kb, pth in sorted(sizes, reverse=True)[:25]:
        print(f"  {kb / 1048576:8.1f} GB  {pth}")


def report_other_runtimes() -> None:
    """QSM-CI scores with docker only on these runners; just report podman/apptainer caches if present."""
    for tool, cache in (("apptainer", Path.home() / ".apptainer" / "cache"),
                        ("podman", Path.home() / ".local" / "share" / "containers")):
        if shutil.which(tool) and cache.exists():
            print(f"{tool}: cache at {cache}: " + sh("du", "-sh", str(cache)).split("\t")[0] + " (not cleaned)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="list what would go; remove nothing")
    ap.add_argument("--image-days", type=float, default=7)
    ap.add_argument("--scratch-days", type=float, default=2)
    ap.add_argument("--diag-days", type=float, default=7)
    ap.add_argument("--drop-pinned", action="store_true",
                    help="also remove images current main pins when unused for --image-days")
    args = ap.parse_args()
    now = time.time()
    clean_images(args, now)
    clean_paths(args, now)
    clean_tmp(args, now)
    report_other_runtimes()
    report_usage()


if __name__ == "__main__":
    main()
