"""Locate the development phantom used by `qsm-ci test`.

Resolution order:
  1. $QSM_CI_DATA — an explicit dataset dir (must contain inputs/ and groundtruth/).
  2. A repo checkout: the nearest data/sim/dev with inputs/ (when run inside a QSM-CI clone).
  3. The user cache (~/.cache/qsm-ci/dev), downloading + extracting the public tarball once.

The dev phantom is small and released openly (both inputs/ and groundtruth/), so local scoring
matches the leaderboard's code exactly. Override the download with $QSM_CI_DEV_URL.
"""

from __future__ import annotations

import os
import tarfile
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_URL = os.environ.get(
    "QSM_CI_DEV_URL",
    "https://github.com/astewartau/qsm-ci/releases/download/dev-phantom/qsm-ci-dev-phantom.tar.gz",
)


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "qsm-ci"


def _valid(ds: Path) -> bool:
    return (ds / "inputs" / "mask.nii.gz").exists() and (ds / "groundtruth").is_dir()


def _find_repo_dev() -> "Path | None":
    for d in [Path.cwd(), *Path.cwd().parents]:
        cand = d / "data" / "sim" / "dev"
        if _valid(cand):
            return cand
    return None


def _extract_root(tmp: Path) -> Path:
    """Find the directory inside an extracted tarball that holds inputs/ + groundtruth/."""
    if _valid(tmp):
        return tmp
    for sub in sorted(tmp.rglob("inputs")):
        if _valid(sub.parent):
            return sub.parent
    raise SystemExit("downloaded archive did not contain inputs/ + groundtruth/")


def ensure_dataset(force: bool = False, log=print) -> Path:
    env = os.environ.get("QSM_CI_DATA")
    if env:
        ds = Path(env).expanduser()
        if not _valid(ds):
            raise SystemExit(f"$QSM_CI_DATA={ds} has no inputs/ + groundtruth/")
        return ds

    if not force:
        repo = _find_repo_dev()
        if repo:
            return repo

    cache = _cache_dir() / "dev"
    if _valid(cache) and not force:
        return cache

    cache.parent.mkdir(parents=True, exist_ok=True)
    log(f"↓ fetching dev phantom … ({DEFAULT_URL})")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        archive = tmp / "dev.tar.gz"
        try:
            urllib.request.urlretrieve(DEFAULT_URL, archive)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(
                f"could not download the dev phantom ({e}).\n"
                f"Set $QSM_CI_DEV_URL, or $QSM_CI_DATA to a local dataset dir "
                f"(with inputs/ + groundtruth/)."
            )
        with tarfile.open(archive) as tf:
            tf.extractall(tmp / "x")
        root = _extract_root(tmp / "x")
        if cache.exists():
            import shutil
            shutil.rmtree(cache)
        import shutil
        shutil.copytree(root, cache)
    log(f"✓ dev phantom ready at {cache}")
    return cache
