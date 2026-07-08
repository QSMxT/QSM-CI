#!/usr/bin/env python3
"""Publish per-run viewer volumes to a public OSF component and record their URLs in the leaderboard.

The site never serves NIfTI volumes from git or the Pages build — they live on OSF. This uploads
every `results/<id>/{recon,truth,error}.nii.gz` written by `pipeline.py --emit-volumes` to a PUBLIC
OSF component, then patches `results/index.json` so each run carries a `volumes: {kind: url}` map the
viewer loads from. Re-runs overwrite the same files (idempotent).

Env:
  OSF_TOKEN          personal access token with write access to the volumes component
  OSF_VOLUMES_NODE   the *public* OSF node id that stores volumes (NOT the private GT project)

Usage:
  python scripts/publish_volumes.py [results_dir]     # default: ./results
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("recon", "truth", "error")
WB = "https://files.osf.io/v1/resources/{node}/providers/osfstorage"


def _req(url: str, token: str, method: str = "GET", data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r) if r.length != 0 else {}


def _list_root(node: str, token: str) -> dict:
    """Map existing top-level osfstorage filename -> waterbutler file id."""
    out, url = {}, WB.format(node=node) + "/?meta="
    data = _req(url, token)
    for item in data.get("data", []):
        attr = item.get("attributes", {})
        if attr.get("kind") == "file":
            out[attr["name"]] = attr["path"].lstrip("/")
    return out


def _upload(node: str, token: str, name: str, blob: bytes, existing: dict) -> str:
    """Create or overwrite <name> at the osfstorage root; return its public WaterButler URL."""
    base = WB.format(node=node)
    if name in existing:  # overwrite the existing file (update endpoint)
        resp = _req(f"{base}/{existing[name]}?kind=file", token, "PUT", blob)
    else:
        resp = _req(f"{base}/?kind=file&name={name}", token, "PUT", blob)
    path = resp["data"]["attributes"]["path"].lstrip("/")
    existing[name] = path
    return f"{base}/{path}"  # public nodes serve this without auth


def main() -> int:
    node, token = os.environ.get("OSF_VOLUMES_NODE"), os.environ.get("OSF_TOKEN")
    if not node or not token:
        print("! OSF_VOLUMES_NODE and OSF_TOKEN must be set", file=sys.stderr)
        return 1
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    index = results / "index.json"
    if not index.exists():
        print("no results/index.json — nothing to publish")
        return 0

    doc = json.loads(index.read_text())
    existing = _list_root(node, token)
    by_id = {r["id"]: r for r in doc.get("runs", [])}
    published = 0

    for run_dir in sorted(results.glob("*/")):
        rid = run_dir.name
        run = by_id.get(rid)
        if run is None:
            continue
        vols = {}
        for kind in KINDS:
            f = run_dir / f"{kind}.nii.gz"
            if not f.exists():
                continue
            name = f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")
            try:
                vols[kind] = _upload(node, token, name, f.read_bytes(), existing)
            except urllib.error.HTTPError as e:
                print(f"  ! {name}: OSF upload failed ({e.code})", file=sys.stderr)
        if vols:
            run["volumes"] = vols
            published += 1
            print(f"  published {rid}: {', '.join(vols)}")

    index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"published volumes for {published} runs -> {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
