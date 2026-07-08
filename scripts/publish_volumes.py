#!/usr/bin/env python3
"""Publish per-run viewer volumes to a public OSF component and record their URLs in the leaderboard.

The site never serves NIfTI volumes from git or the Pages build — they live on OSF. This uploads
every `results/<id>/{recon,truth,error}.nii.gz` written by `pipeline.py --emit-volumes` to a PUBLIC
OSF component, then patches `results/index.json` so each run carries a `volumes: {kind: url}` map the
viewer loads from. Re-runs overwrite the same files (idempotent).

Uses osfclient (`pip install osfclient`).

Env:
  OSF_TOKEN          personal access token with write access to the volumes component
  OSF_VOLUMES_NODE   the *public* OSF node id that stores volumes (e.g. sn52e; NOT the private GT project)

Usage:
  python scripts/publish_volumes.py [results_dir]     # default: ./results
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("recon", "truth", "error")


def _name(rid: str, kind: str) -> str:
    return f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")


def _transient(exc: Exception) -> bool:
    # OSF/WaterButler occasionally return a gateway error mid-request; osfclient surfaces it as a
    # RuntimeError("Response has status code 50x ..."). Also retry raw connection blips.
    s = str(exc)
    return any(c in s for c in ("status code 502", "status code 503", "status code 504")) \
        or exc.__class__.__name__ in ("ConnectionError", "Timeout", "ChunkedEncodingError")


def _retry(desc: str, fn, attempts: int = 5, base: float = 3.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — narrow via _transient below
            if i == attempts - 1 or not _transient(exc):
                raise
            wait = base * (2 ** i)
            print(f"  ! transient OSF error on {desc} ({exc}); retry {i + 1}/{attempts - 1} in {wait:.0f}s",
                  file=sys.stderr)
            time.sleep(wait)


def main() -> int:
    node = os.environ.get("OSF_VOLUMES_NODE")
    token = os.environ.get("OSF_TOKEN")
    if not node or not token:
        print("! OSF_VOLUMES_NODE and OSF_TOKEN must be set", file=sys.stderr)
        return 1
    try:
        from osfclient import OSF
    except ImportError:
        print("! osfclient not installed (pip install osfclient)", file=sys.stderr)
        return 1

    results = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    index = results / "index.json"
    if not index.exists():
        print("no results/index.json — nothing to publish")
        return 0

    doc = json.loads(index.read_text())
    by_id = {r["id"]: r for r in doc.get("runs", [])}

    storage = OSF(token=token).project(node).storage("osfstorage")

    # Upload every run's volumes (overwrite in place), recording the OSF filename per (run, kind).
    want: dict[str, dict[str, str]] = {}
    for run_dir in sorted(results.glob("*/")):
        rid = run_dir.name
        if rid not in by_id:
            continue
        for kind in KINDS:
            f = run_dir / f"{kind}.nii.gz"
            if not f.exists():
                continue
            name = _name(rid, kind)

            def _upload(path=f, nm=name):
                with open(path, "rb") as fp:
                    storage.create_file(nm, fp, force=True, update=True)

            _retry(f"upload {name}", _upload)
            want.setdefault(rid, {})[kind] = name
            print(f"  uploaded {name}")

    # Resolve public download URLs from the storage listing. Verify every upload actually landed —
    # osfclient can PUT against a read-only token and not raise, so never trust "no exception".
    url_by_name = _retry("list storage", lambda: {f.name: f._download_url for f in storage.files})
    missing = [n for kinds in want.values() for n in kinds.values() if n not in url_by_name]
    if missing:
        print(f"! {len(missing)} volume(s) did not appear on OSF after upload (check the token has "
              f"write scope on node '{node}'): {missing[:3]}...", file=sys.stderr)
        return 1

    published = 0
    for rid, kinds in want.items():
        by_id[rid]["volumes"] = {k: url_by_name[n] for k, n in kinds.items()}
        published += 1

    index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"published volumes for {published} runs -> {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
