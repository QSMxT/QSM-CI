#!/usr/bin/env python3
"""Publish the harmonization track's per-column INTERMEDIATE maps to the viewer's HuggingFace repo.

`pipeline.py --emit-intermediates` stages each composed column's upstream artifacts under
`results/_intermediates/<acquisition>/`:

    <field-mapping>__totalfield.nii.gz               the field-mapping stage's output
    <field-mapping>_<bfr>__localfield.nii.gz         the background-removal stage's output

They are shared, not per-run: one total field serves every pipeline starting with that field-mapping
method, and one local field every pipeline through that (field-mapping, bfr) pair. So they upload
into the same `repro/<acquisition>/` directory as the recons, under exactly those basenames — the
submission viewer derives the URL from the pipeline id and needs no index entry to find them.

Idempotent: identical content is deduplicated server-side, so re-publishing is cheap.

Env:
  HF_TOKEN           Hugging Face token with write access
  HF_VOLUMES_REPO    dataset repo that stores volumes, e.g. "qsmxt/qsm-ci-volumes"

Usage:
  python scripts/publish_repro_intermediates.py [results_dir] [--acq ACQUISITION]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_volumes import BATCH, _retry, _url  # noqa: E402  — same batching/retry policy

ROOT = Path(__file__).resolve().parent.parent
INTERMEDIATE_DIR = "_intermediates"


def main() -> int:
    repo = os.environ.get("HF_VOLUMES_REPO")
    token = os.environ.get("HF_TOKEN")
    if not repo or not token:
        print("! HF_VOLUMES_REPO and HF_TOKEN must be set", file=sys.stderr)
        return 1

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only_acq = sys.argv[sys.argv.index("--acq") + 1] if "--acq" in sys.argv else None
    src = (Path(args[0]) if args else ROOT / "results") / INTERMEDIATE_DIR
    if not src.is_dir():
        print(f"no {src} — nothing to publish")
        return 0

    # (path_in_repo, local path) for every staged map, sharded by acquisition exactly like the recons.
    items: list[tuple[str, Path]] = []
    for acq_dir in sorted(d for d in src.iterdir() if d.is_dir()):
        if only_acq and acq_dir.name != only_acq:
            continue
        for f in sorted(acq_dir.glob("*.nii.gz")):
            items.append((f"repro/{acq_dir.name}/{f.name}", f))
    if not items:
        print(f"no intermediates under {src}" + (f" for {only_acq}" if only_acq else ""))
        return 0
    print(f"uploading {len(items)} intermediate maps to {repo} in batches of {BATCH}")

    api = HfApi(token=token)
    _retry("create_repo", lambda: api.create_repo(repo, repo_type="dataset", exist_ok=True))

    failed = 0
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        ops = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=str(path)) for name, path in batch]
        desc = f"batch {start // BATCH + 1}/{(len(items) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=ops, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=o,
                commit_message=f"publish harmonization intermediates ({d})"))
            print(f"  ✓ {desc} ({min(start + BATCH, len(items))}/{len(items)})", flush=True)
        except Exception as exc:  # noqa: BLE001 — best-effort per batch, like publish_volumes
            failed += len(batch)
            print(f"  ! skipping {desc}: {exc}", file=sys.stderr)
    if failed:
        print(f"! {failed} intermediate(s) failed to upload", file=sys.stderr)
        return 1
    print(f"published {len(items)} intermediates -> {_url(repo, 'repro/<acq>/')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
