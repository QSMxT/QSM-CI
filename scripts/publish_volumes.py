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


def _name(rid: str, kind: str, ext: str = "nii.gz", sub: str = "") -> str:
    # HuggingFace rejects a push once any directory holds >10,000 files. The flat root fills up
    # (sim/invivo/chisep already ~10k), so high-volume tracks shard into a subdirectory (`sub`, e.g.
    # "repro/<acquisition>/") — a few hundred files each. `sub` is a clean path; only the id part
    # needs the ~/+ sanitising.
    return sub + f"{rid}__{kind}.{ext}".replace("~", "_").replace("+", "_")


def _subdir(row: dict) -> str:
    """Repo subdirectory for a run's volumes: repro runs shard by acquisition (thousands of files
    would otherwise blow HF's 10k-per-directory limit); every other track keeps the flat root."""
    if row.get("track") == "repro" and row.get("phantom"):
        return f"repro/{row['phantom']}/"
    return ""


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

    # Positional: the results dir. Optional `--runs FILE`: publish ONLY the runs listed in a
    # pipeline.py `--runs-out` file and write the volume URLs back into THAT file (not index.json).
    # This is the scale-ready path — each score job uploads its own slice straight to the Hub and
    # passes on a tiny runs-JSON that already carries the `volumes` URLs, so no volume data is ever
    # gathered centrally (no artifact hop, no 90 GB through one runner). The merge step then just
    # unions these runs-JSONs into index.json. Without --runs it keeps the original behaviour:
    # publish every volume under results/ for the runs in results/index.json, patching index.json.
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    runs_file = None
    if "--runs" in sys.argv:
        runs_file = Path(sys.argv[sys.argv.index("--runs") + 1])
    results = Path(args[0]) if args else ROOT / "results"

    if runs_file is not None:
        if not runs_file.exists():
            print(f"no {runs_file} — nothing to publish")
            return 0
        rows = json.loads(runs_file.read_text())          # a bare list (pipeline.py --runs-out)
        target, is_index = runs_file, False
    else:
        index = results / "index.json"
        if not index.exists():
            print("no results/index.json — nothing to publish")
            return 0
        doc = json.loads(index.read_text())
        rows = doc.get("runs", [])                         # index.json is {"generated":…, "runs":[…]}
        target, is_index = index, True
    by_id = {r["id"]: r for r in rows}

    api = HfApi(token=token)
    try:
        _retry("create_repo", lambda: api.create_repo(repo, repo_type="dataset", exist_ok=True))
    except Exception as exc:  # noqa: BLE001
        print(f"! could not create/access {repo} ({exc}); committing index.json without volumes",
              file=sys.stderr)
        return 0

    # Gather every artifact that belongs to a run in the index: the NIfTI volumes plus, when present,
    # the small resources.json memory/CPU trace. Each item carries its extension so a non-nii.gz
    # artifact (the JSON trace) is named and URL'd correctly.
    items: list[tuple[str, str, str, Path, str]] = []  # (rid, kind, ext, path, sub)
    for run_dir in sorted(results.glob("*/")):
        rid = run_dir.name
        if rid not in by_id:
            continue
        sub = _subdir(by_id[rid])
        for kind in KINDS:
            # χ-separation writes a second "-dia" volume set (recon-dia/truth-dia/error-dia) for its χ−
            # source alongside the plain χ+ set; publish both so the viewer's χ+/χ− toggle can load either.
            for sfx in ("", "-dia"):
                f = run_dir / f"{kind}{sfx}.nii.gz"
                if f.exists():
                    items.append((rid, kind + sfx, "nii.gz", f, sub))
        rf = run_dir / "resources.json"
        if rf.exists():
            items.append((rid, "resources", "json", rf, sub))
        gf = run_dir / "regions.json"   # per-run regional stats; the web fetches one file per run
        if gf.exists():
            items.append((rid, "regions", "json", gf, sub))
    if not items:
        print("no volumes on disk — nothing to publish")
        return 0
    print(f"uploading {len(items)} artifacts to {repo} in batches of {BATCH}")

    want: dict[str, dict[str, str]] = {}
    failed = 0
    consecutive_fail = 0
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        ops = [CommitOperationAdd(path_in_repo=_name(rid, kind, ext, sub), path_or_fileobj=str(path))
               for rid, kind, ext, path, sub in batch]
        desc = f"batch {start // BATCH + 1}/{(len(items) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=ops, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=o,
                commit_message=f"publish volumes ({d})"))
            for rid, kind, ext, _, sub in batch:
                want.setdefault(rid, {})[kind] = _url(repo, _name(rid, kind, ext, sub))
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
        # The resources trace and the per-region stats aren't NiiVue volumes — surface each as its own
        # top-level URL (the viewer graphs resources; the regional views fetch regions), and keep the
        # nii.gz volumes under `volumes` as before.
        res_url = kinds.pop("resources", None)
        if res_url:
            by_id[rid]["resources_url"] = res_url
        reg_url = kinds.pop("regions", None)
        if reg_url:
            by_id[rid]["regions_url"] = reg_url
        if kinds:
            by_id[rid]["volumes"] = kinds
        if res_url or reg_url or kinds:
            published += 1

    # Write the URLs back into whichever file sourced the ids: the central index.json (dict), or the
    # per-job runs-JSON (bare list) whose rows we patched in place via by_id.
    payload = doc if is_index else rows
    target.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"published volumes for {published} runs -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
