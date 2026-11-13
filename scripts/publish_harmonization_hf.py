#!/usr/bin/env python3
"""Upload harmonization acquisitions to a Hugging Face dataset and wire them into the registry.

This replaces publish_harmonization_osf.sh for new uploads: OSF Projects stop taking new components on
16 Nov 2026 and go read-only on 19 Feb 2027. The EMTP traveling-head inputs live in the PRIVATE
dataset qsmxt/qsmci-emtp-inputs until they are published (then flip it public on the Hub; nothing
here changes). OSF keeps the read-only copy that fetch_dataset.sh falls back to.

Each acquisition under data/harmonization/<acq>/ is zipped exactly like the OSF upload did (its
`inputs/` tree at the zip root, the layout fetch_dataset.sh `prepacked: true` expects), uploaded as
qsmci-inputs/<acq>.zip, and its registry entry (scripts/datasets.json) gets `hf_repo`, `hf_path` and
`sha256`. Zips are built one at a time in $TMPDIR and deleted once their batch is committed.

    HF_TOKEN=... python scripts/publish_harmonization_hf.py 's0*'            # EMTP acquisitions
    HF_TOKEN=... python scripts/publish_harmonization_hf.py 's0*' --dry-run  # list what would go up

An acquisition whose registry entry already names this repo with the same sha256 as the remote file
is skipped, so an interrupted run resumes. Re-packing an acquisition gives a zip with new bytes (zip
timestamps): it is uploaded as a new revision of the same path and the registry's sha256 follows.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scripts" / "datasets.json"
DEFAULT_REPO = "qsmxt/qsmci-emtp-inputs"
BATCH_BYTES = 1_500_000_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def wire_registry(text: str, key: str, repo: str, hf_path: str, digest: str) -> str:
    """Set hf_repo/hf_path/sha256 on one entry, editing the text in place so the registry's
    hand-kept formatting (inline lists etc.) survives. Existing values are replaced."""
    m = re.search(r'\n  "%s": \{\n(.*?)\n  \}' % re.escape(key), text, re.S)
    if not m:
        raise SystemExit(f"{key}: not in scripts/datasets.json — add its registry entry first")
    body = m.group(1)
    for field in ("hf_repo", "hf_path", "sha256"):
        body = re.sub(r',\n    "%s": "[^"]*"' % field, "", body)
        body = re.sub(r'\n    "%s": "[^"]*",' % field, "", body)
    body += f',\n    "hf_repo": "{repo}",\n    "hf_path": "{hf_path}",\n    "sha256": "{digest}"'
    return text[:m.start(1)] + body + text[m.end(1):]


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glob", nargs="?", default="s0*", help="acquisition glob under data/harmonization (default s0*: EMTP)")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "harmonization")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    acqs = sorted(p for p in a.data.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and fnmatch.fnmatch(p.name, a.glob) and (p / "inputs").is_dir())
    if not acqs:
        raise SystemExit(f"no acquisitions matching {a.glob!r} under {a.data}")
    reg_text = REGISTRY.read_text()
    reg = json.loads(reg_text)
    if a.dry_run:
        for p in acqs:
            print(f"would upload {p.name} -> {a.repo}:qsmci-inputs/{p.name}.zip"
                  + ("" if p.name in reg else "  (NOT in the registry)"))
        return 0

    from huggingface_hub import CommitOperationAdd, HfApi
    token = os.environ.get("HF_TOKEN") or sys.exit("set HF_TOKEN (a token with write access to the repo)")
    api = HfApi(token=token)
    # A new repo is created private: the inputs are released by flipping it public on the Hub.
    api.create_repo(a.repo, repo_type="dataset", private=True, exist_ok=True)
    remote = {s.rfilename: s.lfs.sha256 for s in
              api.repo_info(a.repo, repo_type="dataset", files_metadata=True).siblings if s.lfs}

    tmp = Path(tempfile.mkdtemp(prefix="hfpub-", dir=os.environ.get("TMPDIR")))
    batch: list = []
    size = 0

    def commit() -> None:
        nonlocal batch, size, reg_text
        if not batch:
            return
        api.create_commit(a.repo, repo_type="dataset", commit_message=f"Add {len(batch)} harmonization acquisition(s)",
                          operations=[CommitOperationAdd(path_in_repo=hp, path_or_fileobj=str(z)) for _, hp, z, _ in batch])
        for key, hp, z, digest in batch:
            reg_text = wire_registry(reg_text, key, a.repo, hp, digest)
            z.unlink()
            print(f"  uploaded {hp} ({digest[:12]})")
        REGISTRY.write_text(reg_text)  # after every batch, so an interrupted run keeps what went up
        batch, size = [], 0

    for p in acqs:
        key, hp = p.name, f"qsmci-inputs/{p.name}.zip"
        if key not in reg:
            raise SystemExit(f"{key}: not in scripts/datasets.json — add its registry entry first")
        d = reg[key]
        if d.get("hf_repo") == a.repo and d.get("sha256") and remote.get(hp) == d["sha256"]:
            continue
        z = tmp / f"{key}.zip"
        subprocess.run(["zip", "-q", "-r", str(z), "inputs"], cwd=p, check=True)
        batch.append((key, hp, z, sha256(z)))
        size += z.stat().st_size
        if size >= BATCH_BYTES:
            commit()
    commit()
    tmp.rmdir()
    print(f"done — {a.repo}; registry entries updated in {REGISTRY.relative_to(ROOT)} (run scripts/gen_manifest.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
