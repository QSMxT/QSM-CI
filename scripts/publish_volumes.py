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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("recon", "truth", "error")


def _name(rid: str, kind: str) -> str:
    return f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")


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
            with open(f, "rb") as fp:
                storage.create_file(name, fp, force=True, update=True)
            want.setdefault(rid, {})[kind] = name
            print(f"  uploaded {name}")

    # Resolve public download URLs from the storage listing. Verify every upload actually landed —
    # osfclient can PUT against a read-only token and not raise, so never trust "no exception".
    url_by_name = {f.name: f._download_url for f in storage.files}
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
