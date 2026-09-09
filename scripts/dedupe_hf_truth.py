#!/usr/bin/env python3
"""One-off: collapse the per-run ground-truth copies on the Hugging Face volumes repo into one
shared file per (phantom, artifact), and repoint results/index.json at it.

Before publish_volumes.py learned to share ground truth, every scored run uploaded its own copy of
the phantom's truth as `<run-id>__truth.nii.gz` — hundreds of byte-identical files. The Hub should
hold exactly one copy: `truth/<phantom>/<artifact>.nii.gz` (the same layout publish_volumes.py now
writes). This script:

  1. reads results/index.json and finds every run whose `volumes.truth` / `volumes.truth-dia` URL is
     a legacy per-run file;
  2. lists the repo tree WITH LFS metadata, so every file's sha256 is known without downloading;
  3. groups the legacy files by content and gives each distinct content one shared name
     (publish_volumes.assign_truth_names — a second, different content for the same phantom/artifact
     gets a `-<sha8>` suffix rather than overwriting);
  4. downloads ONE source file per shared name and uploads it under that name (skipped when the
     shared file already exists with the same sha, so re-runs are no-ops);
  5. rewrites the rows' truth URLs and saves index.json — commit that with git yourself;
  6. and ONLY in a second, opt-in pass, removes the per-run copies.

The two passes are separate on purpose. Deleting a file the deployed index still points at breaks
the site, so the rewritten index has to reach production BEFORE the old files go. See `deletable()`
for the two guards on what may be removed at all — neither of which the original version had, and
one of which would have deleted 165 volumes the live site was serving.

Deleted files stay in the repo's git/LFS history until it is squashed: run the squash-volumes
workflow (scripts/squash_hf_history.py) afterwards if the storage matters.

Env:  HF_TOKEN (write access), HF_VOLUMES_REPO (default qsmxt/qsm-ci-volumes)
Usage:
  # 1. plan (touches nothing)
  python scripts/dedupe_hf_truth.py --dry-run --index results/index.json --index /other/index.json
  # 2. upload the shared files and repoint the FIRST index; commit and deploy it
  python scripts/dedupe_hf_truth.py --index results/index.json --index /other/index.json
  # 3. once that index is live, remove the per-run copies
  python scripts/dedupe_hf_truth.py --index results/index.json --index /other/index.json --delete-legacy

Pass `--index` for EVERY index that references this repo. Anything referenced by any of them is
protected; anything unaccounted for is reported and kept, never deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from publish_volumes import TRUTH_PREFIX, _url, assign_truth_names, truth_name  # noqa: E402

LEGACY = re.compile(r"__truth(-dia)?\.nii\.gz$")
TRUTH_KINDS = ("truth", "truth-dia")


def _path_of(url: str, repo: str) -> str | None:
    base = _url(repo, "")
    return url[len(base):] if url.startswith(base) else None


def deletable(legacy_in_repo, repointed: set, referenced_elsewhere: set,
              shared_sha: set, sha_of: dict) -> tuple[list, list]:
    """Split legacy files into (safe to delete, must keep with a reason).

    THREE conditions, all required. The first is the one that matters:

    * **We must have just repointed this exact file's reference.** Deletion is only ever the tail of
      a repoint we performed, never an inference from silence. The original version deleted whatever
      the single index it was handed did not mention — but no one index covers this repo. In 2026-09
      the deployed results/index.json held 1,162 runs and the HPC's held 17,195, with 234 runs in the
      deployed one and absent from the other; running on the HPC would have destroyed 165 truth
      volumes the live site was serving. A file nothing we processed references is REPORTED and kept,
      because "no index I was given mentions it" is not evidence that no index does.
    * **No other supplied index may reference it** (--index is repeatable), so passing more indexes
      can only ever protect more files, never fewer.
    * **Its bytes must already be preserved** under `truth/` with the same sha256, so deletion can
      never be what loses content, and the pass is safe to repeat or interrupt.
    """
    delete, keep = [], []
    for path in legacy_in_repo:
        sha = sha_of.get(path)
        if path in referenced_elsewhere:
            keep.append((path, "referenced by another index"))
        elif path not in repointed:
            keep.append((path, "not repointed by this run — no index I was given references it"))
        elif sha is None:
            keep.append((path, "no sha256 (not LFS?) — cannot prove the content is preserved"))
        elif sha not in shared_sha:
            keep.append((path, "no shared truth/ file has this content"))
        else:
            delete.append(path)
    return delete, keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="plan only; no uploads, deletes or index write")
    ap.add_argument("--index", type=Path, action="append", dest="indexes", metavar="PATH",
                    help="an index that references this repo; repeat for every one that does. The "
                         "FIRST is the one rewritten. Files referenced by any of them are never "
                         "deleted. (default: results/index.json)")
    ap.add_argument("--delete-legacy", action="store_true",
                    help="second phase: remove the per-run copies. Run this only AFTER the rewritten "
                         "index is deployed, otherwise the live site points at files that are gone.")
    args = ap.parse_args()
    args.indexes = args.indexes or [ROOT / "results" / "index.json"]
    args.index = args.indexes[0]

    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi, hf_hub_download

    repo = os.environ.get("HF_VOLUMES_REPO", "qsmxt/qsm-ci-volumes")
    token = os.environ.get("HF_TOKEN")
    if not token and not args.dry_run:
        print("! HF_TOKEN must be set (or use --dry-run)", file=sys.stderr)
        return 1
    api = HfApi(token=token)

    doc = json.loads(args.index.read_text())
    rows = doc["runs"]

    # 1. legacy truth references. `legacy_refs` drives the rewrite and so covers only the index being
    #    rewritten; `referenced` is the union over EVERY index supplied and is what protects files
    #    from deletion. The two are deliberately different sets.
    legacy_refs: dict[tuple[str, str], str] = {}
    for r in rows:
        for kind in TRUTH_KINDS:
            url = (r.get("volumes") or {}).get(kind)
            path = _path_of(url, repo) if url else None
            if path and LEGACY.search(path):
                legacy_refs[(r["id"], kind)] = path
    print(f"{len(legacy_refs)} legacy per-run truth reference(s) in {args.index}")

    referenced: set[str] = set()
    for idx in args.indexes:
        if not idx.exists():
            sys.exit(f"! {idx} does not exist — refusing to run with an index list I cannot read.")
        n = 0
        for r in json.loads(idx.read_text())["runs"]:
            for kind in TRUTH_KINDS:
                url = (r.get("volumes") or {}).get(kind)
                path = _path_of(url, repo) if url else None
                if path and LEGACY.search(path):
                    referenced.add(path); n += 1
        if idx != args.index:
            print(f"  + {n} legacy reference(s) from {idx} (protected, not rewritten)")

    # 2. repo tree with LFS sha256 per file
    sha_of: dict[str, str] = {}
    for entry in api.list_repo_tree(repo, repo_type="dataset", recursive=True, expand=True):
        lfs = getattr(entry, "lfs", None)
        sha = getattr(lfs, "sha256", None) if lfs is not None else None
        if sha:
            sha_of[entry.path] = sha
    legacy_in_repo = sorted(p for p in sha_of if LEGACY.search(p))
    print(f"{len(sha_of)} LFS file(s) in {repo}; {len(legacy_in_repo)} legacy per-run truth file(s)")

    # 3. one shared name per distinct content
    by_id = {r["id"]: r for r in rows}
    entries, missing = [], []
    for (rid, kind), path in legacy_refs.items():
        sha = sha_of.get(path)
        if sha is None:
            missing.append((rid, kind, path))
            continue
        entries.append(((rid, kind), sha, truth_name(by_id[rid], kind)))
    by_sha, refs = assign_truth_names(entries)
    if missing:
        print(f"  ! {len(missing)} referenced legacy file(s) are gone from the repo (dead URLs):")
        for rid, kind, path in missing[:10]:
            print(f"      {rid} {kind} -> {path}")
    # 4. which shared names need creating (absent, or present with different bytes)
    sha_to_source = {}
    for (rid, kind), sha, _ in entries:
        sha_to_source.setdefault(sha, legacy_refs[(rid, kind)])
    to_create = {name: sha_to_source[sha] for sha, name in by_sha.items() if sha_of.get(name) != sha}
    print("\nplan:")
    for sha, name in sorted(by_sha.items(), key=lambda kv: kv[1]):
        n = sum(1 for k, v in refs.items() if v == name)
        state = "create" if name in to_create else "exists"
        print(f"  {state:6s} {name:48s} <- {n:4d} run(s), sha {sha[:12]}")
    # The shared files that will exist once step 5 has run, by content — the "bytes are preserved"
    # guard checks against this, so a first pass plans honestly before anything is uploaded.
    shared_sha = set(by_sha) | {sha for path, sha in sha_of.items() if path.startswith(TRUTH_PREFIX)}
    repointed = set(legacy_refs.values())                  # files whose reference this run rewrites
    others = referenced - repointed                        # held by an index we are NOT rewriting
    to_delete, kept = deletable(legacy_in_repo, repointed, others, shared_sha, sha_of)
    print(f"  {len(to_delete)} legacy file(s) are removable; {len(kept)} kept")
    reasons = Counter(why for _, why in kept)
    for why, n in reasons.most_common():
        print(f"      keep {n:5d}: {why}")
    if not args.delete_legacy:
        print("  (deleting nothing this pass — rerun with --delete-legacy once the rewritten index "
              "is DEPLOYED, or the live site will point at files that are gone)")
    dup_names = [n for n, c in Counter(by_sha.values()).items() if c > 1]
    assert not dup_names, dup_names  # assign_truth_names guarantees uniqueness

    if args.dry_run:
        print("\n--dry-run: nothing changed")
        return 0

    # Upload the shared files first (so no run points at a name that doesn't exist yet) …
    if to_create:
        with tempfile.TemporaryDirectory() as tmp:
            ops = []
            for name, src in sorted(to_create.items()):
                local = hf_hub_download(repo, src, repo_type="dataset", cache_dir=tmp, token=token)
                ops.append(CommitOperationAdd(path_in_repo=name, path_or_fileobj=local))
                print(f"  ↑ {name}  (from {src})")
            api.create_commit(repo, repo_type="dataset", operations=ops,
                              commit_message=f"share ground truth: {len(ops)} file(s) under {TRUTH_PREFIX}")
    # … then drop the per-run copies, but only in the explicit second phase and only those that
    # cleared BOTH guards. Ordering matters: the index rewritten below has to be deployed before the
    # files it used to point at are removed, which is why this is opt-in rather than automatic.
    if args.delete_legacy and to_delete:
        for start in range(0, len(to_delete), 1000):
            chunk = to_delete[start:start + 1000]
            api.create_commit(repo, repo_type="dataset",
                              operations=[CommitOperationDelete(path_in_repo=p) for p in chunk],
                              commit_message=f"remove per-run ground-truth copies ({start + len(chunk)}/{len(to_delete)})")
            print(f"  ✗ deleted {start + len(chunk)}/{len(to_delete)} legacy file(s)")
    elif to_delete:
        print(f"  {len(to_delete)} legacy file(s) left in place (no --delete-legacy)")

    # 6. repoint the index
    for (rid, kind), name in refs.items():
        by_id[rid]["volumes"][kind] = _url(repo, name)
    # Rows whose legacy file was already gone: point them at the shared file for their phantom/artifact
    # when one now exists (they were scored against the same truth); otherwise leave the dead URL.
    names_now = set(by_sha.values())
    for rid, kind, _ in missing:
        want = truth_name(by_id[rid], kind)
        if want in names_now:
            by_id[rid]["volumes"][kind] = _url(repo, want)
    args.index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"\nrewrote {len(refs)} truth URL(s) in {args.index} — review and commit it. "
          "Old blobs remain in repo history until squashed (squash-volumes workflow).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
