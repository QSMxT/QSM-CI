#!/usr/bin/env python3
"""Publish per-run viewer volumes to a public OSF component and record their URLs in the leaderboard.

The site never serves NIfTI volumes from git or the Pages build — they live on OSF. This uploads
every `results/<id>/{recon,truth,error}.nii.gz` written by `pipeline.py --emit-volumes` to a PUBLIC
OSF component, then patches `results/index.json` so each run carries a `volumes: {kind: url}` map the
viewer loads from. Re-runs overwrite the same files (new version), so it's idempotent.

Talks to OSF/WaterButler over plain HTTP (requests) rather than osfclient: osfclient's
create_file(update=True) re-lists EVERY existing file on every single upload — O(N^2), which turned
a ~1000-file publish into a multi-hour hang. Here we list the component once, then PUT each file
directly (create new, or overwrite an existing one by id) — O(N).

Best-effort: a volume that fails after a couple of retries is skipped, never aborting the publish —
the leaderboard scores live in index.json (committed by the workflow regardless). A circuit breaker
bails out early if OSF is genuinely down, so we never grind for hours.

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

import requests

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("recon", "truth", "error")


def _name(rid: str, kind: str) -> str:
    return f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")


def _retry(desc, fn, attempts=3, base=2.0):
    """Retry a request a few times on transient failure (short backoff — uploads are fast now)."""
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if i == attempts - 1:
                raise
            wait = base * (2 ** i)
            print(f"  ! transient error on {desc} ({exc}); retry {i + 1}/{attempts - 1} in {wait:.0f}s",
                  file=sys.stderr)
            time.sleep(wait)


def _list_existing(session, node):
    """One paginated pass over the component: name -> {'id': file id, 'download': url}."""
    out = {}
    url = f"https://api.osf.io/v2/nodes/{node}/files/osfstorage/?page[size]=100"
    while url:
        j = _retry("list", lambda u=url: _ok(session.get(u, timeout=60))).json()
        for f in j.get("data", []):
            a = f.get("attributes", {})
            out[a.get("name")] = {"id": f["id"], "download": f.get("links", {}).get("download")}
        url = j.get("links", {}).get("next")
    return out


def _ok(resp):
    resp.raise_for_status()
    return resp


def main() -> int:
    node = os.environ.get("OSF_VOLUMES_NODE")
    token = os.environ.get("OSF_TOKEN")
    if not node or not token:
        print("! OSF_VOLUMES_NODE and OSF_TOKEN must be set", file=sys.stderr)
        return 1

    results = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    index = results / "index.json"
    if not index.exists():
        print("no results/index.json — nothing to publish")
        return 0

    doc = json.loads(index.read_text())
    by_id = {r["id"]: r for r in doc.get("runs", [])}

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    wb = f"https://files.osf.io/v1/resources/{node}/providers/osfstorage/"

    try:
        existing = _list_existing(session, node)  # ONE listing, not per-file
    except Exception as exc:  # noqa: BLE001
        print(f"! could not list OSF storage ({exc}); committing index.json without volumes",
              file=sys.stderr)
        return 0
    print(f"  {len(existing)} files already in the component")

    def _upload(path: Path, name: str) -> str:
        """PUT one file (overwrite existing by id, else create by name); return its download URL."""
        with open(path, "rb") as fp:
            if name in existing:
                resp = _ok(session.put(wb + existing[name]["id"], params={"kind": "file"},
                                       data=fp, timeout=300))
            else:
                resp = _ok(session.put(wb, params={"kind": "file", "name": name},
                                       data=fp, timeout=300))
        return resp.json().get("data", {}).get("links", {}).get("download") \
            or existing.get(name, {}).get("download")

    want: dict[str, dict[str, str]] = {}
    failed = 0
    done = 0
    consecutive_fail = 0
    give_up = False
    for run_dir in sorted(results.glob("*/")):
        if give_up:
            break
        rid = run_dir.name
        if rid not in by_id:
            continue
        for kind in KINDS:
            f = run_dir / f"{kind}.nii.gz"
            if not f.exists():
                continue
            name = _name(rid, kind)
            try:
                url = _retry(f"upload {name}", lambda p=f, n=name: _upload(p, n))
                if url:
                    want.setdefault(rid, {})[kind] = url
                consecutive_fail = 0
                done += 1
                if done % 50 == 0:
                    print(f"  ... {done} uploaded", flush=True)
            except Exception as exc:  # noqa: BLE001 — best-effort per volume
                failed += 1
                consecutive_fail += 1
                print(f"  ! skipping {name}: {exc}", file=sys.stderr)
                if consecutive_fail >= 15:  # circuit breaker: OSF is down, stop grinding
                    print("  ! 15 consecutive upload failures — OSF looks down; giving up on volumes "
                          "and committing the scores.", file=sys.stderr)
                    give_up = True
                    break
    if failed:
        print(f"! {failed} volume(s) failed to upload; committing index.json with the rest",
              file=sys.stderr)

    published = 0
    for rid, kinds in want.items():
        if kinds:
            by_id[rid]["volumes"] = kinds
            published += 1

    index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"published volumes for {published} runs -> {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
