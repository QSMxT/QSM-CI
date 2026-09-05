#!/usr/bin/env python3
"""Publish per-run viewer volumes to a public Hugging Face dataset repo and record their URLs
in the leaderboard.

The site never serves NIfTI volumes from git or the Pages build — they live on the Hugging Face
Hub. This uploads every run's `recon`/`error` volumes (plus its resources/regions JSON) written by
`pipeline.py --emit-volumes`, and each phantom's ground-truth volume ONCE, to a PUBLIC dataset repo,
then patches `results/index.json` so each run carries a `volumes: {kind: url}` map the viewer loads
from. Re-runs overwrite the same paths (new revision), so it's idempotent — and identical content is
deduplicated server-side, so re-publishing unchanged volumes is cheap.

Ground truth is shared, not per run. Every run on a phantom scores against the same truth, so the
Hub holds one `truth/<phantom>/<artifact>.nii.gz` per (phantom, artifact) and every run's
`volumes.truth` URL points at it. pipeline.py stages that file under results/_truth/ and leaves a
`truth.ref` pointer in each run dir; a legacy per-run `truth.nii.gz` (runs scored before this) is
still accepted and folded into the same shared file by content hash, so no duplicate ever reaches
the Hub. (The Hub repo predating this holds hundreds of per-run copies: scripts/dedupe_hf_truth.py
collapses them.)

Why HF (and not OSF, which this replaced): volumes are committed in batches instead of one HTTP
round-trip per file, uploads within a batch run in parallel, and the `resolve/` download URLs are
CDN-backed and send CORS headers — exactly what the in-browser NiiVue viewer needs (OSF's
WaterButler links were slow, flaky, and needed an `&direct` CORS workaround).

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
  python scripts/publish_volumes.py [results_dir]              # default: ./results, patches index.json
  python scripts/publish_volumes.py results --runs runs.json   # one job's slice (pipeline --runs-out)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qsm_ci.stages import STAGES  # noqa: E402 — the stage graph, for produced-artifact lookups

# Per-run volume kinds. Ground truth is handled separately (shared per phantom, see module doc).
KINDS = ("recon", "error")
TRUTH_DIR = "_truth"       # results/_truth/<phantom>/<artifact>.nii.gz, staged by pipeline.py
TRUTH_PREFIX = "truth/"    # Hub path prefix for the shared truths: truth/<phantom>/<artifact>.nii.gz
# Files per Hub commit. HuggingFace rate-limits COMMITS to 128/hour per repo, so this must be large
# enough that a whole publish is a handful of commits, not hundreds (the repro track's ~30k files at
# 64/commit = 463 commits → 429 Too Many Requests partway). 1000 files/commit → ~30 commits for the
# full repro set, and a per-job CI publish (one shard, ~100 files) is a single commit. Each commit
# still preuploads its LFS files individually, so a transient blob failure only retries that blob.
BATCH = 1000


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def truth_artifact(row: dict, kind: str) -> str | None:
    """Which canonical artifact a run's `truth` / `truth-dia` volume is: the primary artifact the
    run's LAST stage produces (a `field-mapping+bfr+dipole` span ends in a dipole -> chimap), or χ−
    for the `-dia` set. None when the row carries no recognisable stage."""
    if kind == "truth-dia":
        return "chi-dia"
    last = (row.get("stage") or "").split("+")[-1]
    stage = STAGES.get(last) or STAGES.get(row.get("stage") or "")
    return stage["produces"][0] if stage else None


def truth_name(row: dict, kind: str) -> str:
    """Hub path for a run's shared ground-truth volume, derived from the row alone (used for legacy
    per-run truth files that carry no pointer): truth/<phantom>/<artifact>.nii.gz. The QSM sim track's
    historical rows have no `phantom`; their phantom is the track's default, `sim`."""
    phantom = row.get("phantom") or row.get("track") or "sim"
    artifact = truth_artifact(row, kind) or kind
    return f"{TRUTH_PREFIX}{phantom}/{artifact}.nii.gz"


def resolve_truth(run_dir: Path, results: Path, row: dict, kind: str) -> tuple[Path, str] | None:
    """Locate a run's ground-truth volume and the Hub path it publishes to.

    Preferred: the `truth{sfx}.ref` pointer pipeline.py writes -> the shared results/_truth/… file,
    published as truth/<phantom>/<artifact>.nii.gz (the pointer's path minus the `_truth/` root).
    Legacy: a per-run `truth{sfx}.nii.gz`, published under the name derived from the row. Returns
    None when the run has no truth (a no-ground-truth track, or a DNF)."""
    sfx = kind[len("truth"):]
    ref = run_dir / f"truth{sfx}.ref"
    if ref.exists():
        rel = ref.read_text().strip()
        path = results / rel
        if path.exists():
            inner = rel[len(TRUTH_DIR) + 1:] if rel.startswith(TRUTH_DIR + "/") else rel
            return path, TRUTH_PREFIX + inner
    legacy = run_dir / f"truth{sfx}.nii.gz"
    if legacy.exists():
        return legacy, truth_name(row, kind)
    return None


def assign_truth_names(entries: list[tuple[object, str, str]]) -> tuple[dict[str, str], dict[object, str]]:
    """Give every distinct ground-truth CONTENT one Hub path.

    `entries` is [(key, sha256, wanted_name)]. Returns (by_sha: sha -> hub_name, refs: key -> hub_name).
    Entries whose bytes hash identical share one name — the first `wanted` seen. Two DIFFERENT contents
    that both want the same name (a phantom regenerated between rescoring rounds) keep the plain name
    for the first and get a `-<sha8>` suffix for the rest, so nothing is silently overwritten and every
    run still points at the bytes it was scored against."""
    by_sha: dict[str, str] = {}
    taken: set[str] = set()
    refs: dict[object, str] = {}
    for key, sha, wanted in entries:
        name = by_sha.get(sha)
        if name is None:
            name = wanted
            if name in taken:  # same name, different bytes
                name = f"{wanted.split('.nii.gz')[0]}-{sha[:8]}.nii.gz"
            by_sha[sha] = name
            taken.add(name)
        refs[key] = name
    return by_sha, refs


def plan_truths(found: list[tuple[str, str, Path, str]]) -> tuple[dict[str, Path], dict[tuple[str, str], str]]:
    """Collapse every run's truth to one upload per distinct content (see assign_truth_names).

    `found` is [(rid, kind, local_path, wanted_name)]. Returns (uploads: hub_name -> local file,
    refs: (rid, kind) -> hub_name)."""
    hashed = {}
    for _, _, path, _ in found:
        if path not in hashed:
            hashed[path] = _sha256(path)
    by_sha, refs = assign_truth_names([((rid, kind), hashed[path], wanted) for rid, kind, path, wanted in found])
    uploads: dict[str, Path] = {}
    for rid, kind, path, _ in found:
        uploads.setdefault(refs[(rid, kind)], path)
    return uploads, refs


def _retry(desc, fn, attempts=3, base=4.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — retried, then re-raised
            if i == attempts - 1:
                raise
            wait = base * (2 ** i)
            print(f"  ! {desc}: {exc} — retry in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)


def main() -> int:
    from huggingface_hub import CommitOperationAdd, HfApi

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

    # Gather every artifact that belongs to a run in the index. Per run: the recon/error NIfTIs,
    # plus, when present, the small resources.json memory/CPU trace and the regions.json stats.
    # Shared: each run's ground truth, resolved to ONE upload per distinct content (plan_truths).
    # `uploads` maps the Hub path to the local file; `refs` says which (run, kind) each path serves —
    # several runs per truth path, exactly one per anything else.
    uploads: dict[str, Path] = {}
    refs: list[tuple[str, str, str]] = []                # (rid, kind, hub_name)
    truths: list[tuple[str, str, Path, str]] = []        # (rid, kind, local_path, wanted_name)
    for run_dir in sorted(results.glob("*/")):
        rid = run_dir.name
        if rid not in by_id:
            continue
        row = by_id[rid]
        sub = _subdir(row)
        # χ-separation writes a second "-dia" volume set (recon-dia/error-dia + a truth-dia pointer)
        # for its χ− source alongside the plain χ+ set; publish both so the viewer's toggle can load either.
        for sfx in ("", "-dia"):
            for kind in KINDS:
                f = run_dir / f"{kind}{sfx}.nii.gz"
                if f.exists():
                    name = _name(rid, kind + sfx, "nii.gz", sub)
                    uploads[name] = f
                    refs.append((rid, kind + sfx, name))
            t = resolve_truth(run_dir, results, row, "truth" + sfx)
            if t is not None:
                truths.append((rid, "truth" + sfx, t[0], t[1]))
        for kind, fname in (("resources", "resources.json"), ("regions", "regions.json")):
            f = run_dir / fname   # resources: memory/CPU trace; regions: per-run regional stats
            if f.exists():
                name = _name(rid, kind, "json", sub)
                uploads[name] = f
                refs.append((rid, kind, name))
    truth_uploads, truth_refs = plan_truths(truths)
    uploads.update(truth_uploads)
    refs.extend((rid, kind, name) for (rid, kind), name in truth_refs.items())
    if not uploads:
        print("no volumes on disk — nothing to publish")
        return 0
    print(f"uploading {len(uploads)} files to {repo} in batches of {BATCH} "
          f"({len(truth_uploads)} shared ground-truth volume(s) for {len(truth_refs)} run(s))")

    landed: set[str] = set()
    failed = 0
    consecutive_fail = 0
    names = sorted(uploads)
    for start in range(0, len(names), BATCH):
        batch = names[start:start + BATCH]
        ops = [CommitOperationAdd(path_in_repo=n, path_or_fileobj=str(uploads[n])) for n in batch]
        desc = f"batch {start // BATCH + 1}/{(len(names) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=ops, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=o,
                commit_message=f"publish volumes ({d})"))
            landed.update(batch)
            consecutive_fail = 0
            print(f"  ✓ {desc} ({min(start + BATCH, len(names))}/{len(names)})", flush=True)
        except Exception as exc:  # noqa: BLE001 — best-effort per batch
            failed += len(batch)
            consecutive_fail += 1
            print(f"  ! skipping {desc}: {exc}", file=sys.stderr)
            if consecutive_fail >= 3:  # circuit breaker: the Hub is down, stop grinding
                print("  ! 3 consecutive batch failures — Hugging Face looks down; giving up on "
                      "volumes and committing the scores.", file=sys.stderr)
                break
    if failed:
        print(f"! {failed} file(s) failed to upload; committing index.json with the rest",
              file=sys.stderr)

    want: dict[str, dict[str, str]] = {}
    for rid, kind, name in refs:
        if name in landed:
            want.setdefault(rid, {})[kind] = _url(repo, name)

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
