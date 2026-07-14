#!/usr/bin/env python3
"""One-off migration: move existing viewer volumes from OSF to Hugging Face.

Reads `results/index.json`, downloads every volume from its current (public) OSF URL, uploads it
to the HF dataset repo with the same flat naming `publish_volumes.py` uses, and rewrites each
run's `volumes` map to the HF URLs. Commit the patched index.json afterwards to switch the viewer
over (the migrate-volumes workflow does this automatically).

Works batch-at-a-time (download 64 -> commit to HF -> delete local copies -> rewrite index.json),
so disk use stays bounded (~1-2 GB) and an interrupted run loses at most one batch. Safe to
re-run: runs whose URLs already point at huggingface.co are skipped.

Env:
  HF_TOKEN           Hugging Face token with write access
  HF_VOLUMES_REPO    dataset repo id, e.g. "qsmxt/qsm-ci-volumes" (created if missing)

Usage:
  python scripts/migrate_volumes_to_hf.py [results_dir]     # default: ./results
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".hfmigrate"
BATCH = 64


def _name(rid: str, kind: str) -> str:
    return f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")


def _url(repo: str, name: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{name}"


def _direct(url: str) -> str:
    """OSF WaterButler links need `action=download&direct` to reliably serve file bytes."""
    if "action=download" in url:
        return url
    return url + ("&" if "?" in url else "?") + "action=download&direct"


def _retry(desc, fn, attempts=3, base=4.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if i == attempts - 1:
                raise
            wait = base * (2 ** i)
            print(f"  ! {desc}: {exc}; retry {i + 1}/{attempts - 1} in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)


def main() -> int:
    repo = os.environ.get("HF_VOLUMES_REPO")
    token = os.environ.get("HF_TOKEN")
    if not repo or not token:
        print("! HF_VOLUMES_REPO and HF_TOKEN must be set", file=sys.stderr)
        return 1

    results = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    index = results / "index.json"
    doc = json.loads(index.read_text())

    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    session = requests.Session()

    todo: list[tuple[dict, str, str]] = []  # (run, kind, name)
    for run in doc.get("runs", []):
        for kind, url in (run.get("volumes") or {}).items():
            if "huggingface.co" in url:
                continue  # already migrated
            todo.append((run, kind, _name(run["id"], kind)))
    if not todo:
        print("nothing to migrate — all volume URLs already point at Hugging Face")
        return 0
    total_batches = (len(todo) + BATCH - 1) // BATCH
    print(f"migrating {len(todo)} volumes from OSF to {repo} in {total_batches} batches")

    migrated = 0
    failed_dl = 0
    for start in range(0, len(todo), BATCH):
        batch = todo[start:start + BATCH]
        desc = f"batch {start // BATCH + 1}/{total_batches}"

        # 1. download this batch from OSF
        fetched: list[tuple[dict, str, str, Path]] = []
        for run, kind, name in batch:
            local = CACHE / name
            if not local.exists():
                url = _direct(run["volumes"][kind])
                try:
                    def _dl(u=url, p=local):
                        r = session.get(u, timeout=300)
                        r.raise_for_status()
                        if not r.content:
                            raise RuntimeError("empty body")
                        p.write_bytes(r.content)
                    _retry(f"download {name}", _dl)
                except Exception as exc:  # noqa: BLE001
                    failed_dl += 1
                    print(f"  ! could not download {name} from OSF: {exc} — leaving its OSF URL",
                          file=sys.stderr)
                    continue
            fetched.append((run, kind, name, local))
        if not fetched:
            continue

        # 2. one HF commit for the batch, then patch URLs + persist index immediately
        ops = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=str(local))
               for _, _, name, local in fetched]
        _retry(desc, lambda o=ops, d=desc: api.create_commit(
            repo, repo_type="dataset", operations=o, commit_message=f"migrate volumes ({d})"))
        for run, kind, name, _ in fetched:
            run["volumes"][kind] = _url(repo, name)
        migrated += len(fetched)
        index.write_text(json.dumps(doc, indent=2) + "\n")

        # 3. free the disk before the next batch
        for _, _, _, local in fetched:
            local.unlink(missing_ok=True)
        print(f"  ✓ {desc} ({migrated}/{len(todo)})", flush=True)

    if failed_dl:
        print(f"! {failed_dl} volume(s) could not be fetched from OSF (kept their OSF URLs); "
              "re-run to retry", file=sys.stderr)
    print(f"done: {migrated}/{len(todo)} volumes migrated; index updated -> {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
