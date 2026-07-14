#!/usr/bin/env python3
"""Publish per-run viewer volumes to a public Hugging Face dataset repo and record their URLs
in the leaderboard.

The site never serves NIfTI volumes from git or the Pages build — they live on the Hugging Face
Hub. This uploads every `results/<id>/{recon,truth,error}.nii.gz` written by
`pipeline.py --emit-volumes` to a PUBLIC dataset repo, then patches `results/index.json` so each
run carries a `volumes: {kind: url}` map the viewer loads from. Re-runs overwrite the same paths
(new revision), so it's idempotent — and identical content is deduplicated server-side, so
re-publishing unchanged volumes is cheap.

Why HF (and not OSF, which this replaced): volumes are committed in batches of ~64 files per
commit instead of one HTTP round-trip per file, uploads within a batch run in parallel, and the
`resolve/` download URLs are CDN-backed and send CORS headers — exactly what the in-browser
NiiVue viewer needs (OSF's WaterButler links were slow, flaky, and needed an `&direct` CORS
workaround).

Download URLs are deterministic (`https://huggingface.co/datasets/<repo>/resolve/main/<file>`),
so they can be recorded even before a batch lands.

Best-effort: a batch that fails after a few retries is skipped, never aborting the publish — the
leaderboard scores live in index.json (committed by the workflow regardless). A circuit breaker
bails out early if the Hub is genuinely down, so we never grind for hours.

Env:
  HF_TOKEN           Hugging Face token with write access (repo Settings -> Actions secret)
  HF_VOLUMES_REPO    dataset repo id that stores volumes, e.g. "qsmxt/qsm-ci-volumes"
                     (created automatically as a public dataset repo if it doesn't exist)

Usage:
  python scripts/publish_volumes.py [results_dir]     # default: ./results
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("recon", "truth", "error")
BATCH = 64  # files per Hub commit — small enough that a failed batch is cheap to retry/skip


def _name(rid: str, kind: str) -> str:
    return f"{rid}__{kind}.nii.gz".replace("~", "_").replace("+", "_")


def _url(repo: str, name: str) -> str:
    """Stable public download URL; `resolve/` redirects to the CDN and sends CORS headers."""
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{name}"


def _retry(desc, fn, attempts=3, base=4.0):
    """Retry a Hub call a few times on transient failure."""
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


def main() -> int:
    repo = os.environ.get("HF_VOLUMES_REPO")
    token = os.environ.get("HF_TOKEN")
    if not repo or not token:
        print("! HF_VOLUMES_REPO and HF_TOKEN must be set", file=sys.stderr)
        return 1

    results = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
    index = results / "index.json"
    if not index.exists():
        print("no results/index.json — nothing to publish")
        return 0

    doc = json.loads(index.read_text())
    by_id = {r["id"]: r for r in doc.get("runs", [])}

    api = HfApi(token=token)
    try:
        _retry("create_repo", lambda: api.create_repo(repo, repo_type="dataset", exist_ok=True))
    except Exception as exc:  # noqa: BLE001
        print(f"! could not create/access {repo} ({exc}); committing index.json without volumes",
              file=sys.stderr)
        return 0

    # Gather every volume that belongs to a run in the index.
    items: list[tuple[str, str, Path]] = []  # (rid, kind, path)
    for run_dir in sorted(results.glob("*/")):
        rid = run_dir.name
        if rid not in by_id:
            continue
        for kind in KINDS:
            f = run_dir / f"{kind}.nii.gz"
            if f.exists():
                items.append((rid, kind, f))
    if not items:
        print("no volumes on disk — nothing to publish")
        return 0
    print(f"uploading {len(items)} volumes to {repo} in batches of {BATCH}")

    want: dict[str, dict[str, str]] = {}
    failed = 0
    consecutive_fail = 0
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        ops = [CommitOperationAdd(path_in_repo=_name(rid, kind), path_or_fileobj=str(path))
               for rid, kind, path in batch]
        desc = f"batch {start // BATCH + 1}/{(len(items) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=ops, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=o,
                commit_message=f"publish volumes ({d})"))
            for rid, kind, _ in batch:
                want.setdefault(rid, {})[kind] = _url(repo, _name(rid, kind))
            consecutive_fail = 0
            print(f"  ✓ {desc} ({min(start + BATCH, len(items))}/{len(items)})", flush=True)
        except Exception as exc:  # noqa: BLE001 — best-effort per batch
            failed += len(batch)
            consecutive_fail += 1
            print(f"  ! skipping {desc}: {exc}", file=sys.stderr)
            if consecutive_fail >= 3:  # circuit breaker: the Hub is down, stop grinding
                print("  ! 3 consecutive batch failures — Hugging Face looks down; giving up on "
                      "volumes and committing the scores.", file=sys.stderr)
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
