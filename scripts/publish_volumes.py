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
  python scripts/publish_volumes.py --prune [--prune-dry-run]  # also delete orphaned volumes
  python scripts/publish_volumes.py --prune --prune-flat --index /other/index.json
                                                              # ALSO clean retired runs' volumes
                                                              # from the flat root (see _prune_flat)

`--prune` (index mode only) deletes repo files this publish did not produce and index.json does
not reference. Uploading alone is an UPSERT: a run that stops being produced — a method that DNF'd
this time but succeeded last time, or one dropped from the matrix — leaves its old volume behind,
and the viewer serves that stale recon forever. Pruning is what makes a recompute actually replace
the previous one. See `_prune` for the (deliberately narrow) safety scope.
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
# The artifact kinds a RUN owns — every `kind` this script uploads per run: KINDS and their χ-sep
# "-dia" twins, the truth pointer, and the two JSON sidecars. Prune deletes ONLY these (see
# _run_artifact): a file whose kind is not in here does not belong to any single run, so no
# per-run bookkeeping can vouch for it and prune must not judge it.
RUN_ARTIFACTS = frozenset({"recon", "error", "truth", "resources", "regions"})
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


def _delete_op(path: str):
    """A Hub delete operation. Indirect so the prune tests can exercise the real logic without
    huggingface_hub installed — the rest of this module already imports it lazily inside main()."""
    from huggingface_hub import CommitOperationDelete
    return CommitOperationDelete(path_in_repo=path)


def _run_artifact(path: str, sub: str) -> "tuple[str, str] | None":
    """(run id, kind) if `path` is a per-run artifact, else None.

    Remote names are `<sub><rid>__<kind>.<ext>` (see _name). The kind is what identifies a file as
    belonging to a run — and it is exactly the discriminator prune needs, because the repo also
    holds files that belong to NO run and are addressed by naming convention instead of by any URL
    recorded in index.json:

        repro/<acq>/<acq>__magnitude.nii.gz            one per acquisition
        repro/<acq>/<fm>__totalfield.nii.gz            one per field-mapping method
        repro/<acq>/<fm>_<bfr>__localfield.nii.gz      one per (field mapping, bg removal) pair

    Hundreds of pipelines share each of those, so there is no run to record them against; the viewer
    reconstructs their URLs from the naming pattern (see web/js/viewer.js reproMagnitudeUrl /
    reproTotalfieldUrl / reproLocalfieldUrl). They are therefore invisible to BOTH of prune's tests —
    not uploaded by a per-run publish, and never named in index.json — so a keep-set built from runs
    alone classes all 621 of them as orphans. Restricting prune to recognised run artifacts makes
    them out of scope by construction rather than by a blacklist that the next shared artifact would
    silently fall out of.
    """
    rest = path[len(sub):] if sub and path.startswith(sub) else path
    if "__" not in rest:
        return None
    rid, tail = rest.rsplit("__", 1)
    kind = tail.split(".", 1)[0]
    base = kind[:-4] if kind.endswith("-dia") else kind      # recon-dia / error-dia / truth-dia
    return (rid, kind) if base in RUN_ARTIFACTS and rid else None


def _prune_flags(argv: list) -> tuple[bool, bool]:
    """(prune, dry_run) from argv.

    `--prune-dry-run` IMPLIES `--prune`. A dry run is the safe thing you reach for first, so it must
    not be a silent no-op — that is exactly what it was when an older copy of this script (which had
    no prune at all) was handed the flag: unknown `--` args are filtered out of the positional list,
    so it published, pruned nothing, printed nothing about pruning, and exited 0.
    """
    dry = "--prune-dry-run" in argv
    return ("--prune" in argv or dry), dry


def _extra_indexes(argv: list) -> list:
    """Every --index PATH given, for the flat-root prune's completeness check."""
    return [Path(argv[i + 1]) for i, a in enumerate(argv) if a == "--index" and i + 1 < len(argv)]


def _prune(api, repo, uploaded: set, keep_extra: set, scopes: set, dry_run: bool,
           superseded: set = frozenset()) -> int:
    """Delete volumes under `scopes` that are no longer produced. Returns the number deleted.

    Uploading is an upsert, so a run that stops being produced keeps its old file forever and the
    viewer serves a recon computed from inputs that no longer exist. This removes those.

    Four deliberate safety limits, because this deletes published data:

    * **Sharded subdirectories only, never the flat root.** Scope is the set of `sub` prefixes this
      publish wrote into (e.g. `repro/<acquisition>/`). The flat root mixes tracks whose runs may
      not be in this results dir at all — pruning it from a partial index would delete another
      track's volumes.
    * **Never the shared ground truth.** `truth/<phantom>/<artifact>.nii.gz` is referenced by every
      run on that phantom, including runs outside this publish, and is deduplicated by content
      hash. Housekeeping there belongs to scripts/dedupe_hf_truth.py, not here.
    * **Keep anything index.json still points at.** A volume can be live in the index but absent
      from this machine's `results/` (published by an earlier job, or cleaned up). Uploaded paths
      alone are not the keep set; URLs already recorded in the index count too.
    * **Only recognised per-run artifacts.** See `_run_artifact`. Prune deletes a file only when it
      can say which run and which artifact it is; anything it cannot classify is left alone. This
      replaced a "refuse to delete more than half the scope" rule, which measured the wrong thing:
      it let a 621-file deletion of live shared intermediates through at 1% of the scope, while it
      would have blocked the legitimate cleanup of a retired method (~1,200 runs) and pushed the
      operator towards a --prune-force habit that disables the check exactly when it matters.
      Proportion of files says nothing about whether a file is needed; attribution does.

    The guard against a PARTIAL publish (the real risk the proportion rule was groping at — a
    truncated index makes every absent run look retired) lives at the call site, which is where the
    published-vs-indexed run counts are known.
    """
    scopes = {s for s in scopes if s and not s.startswith(TRUTH_PREFIX)}
    if not scopes:
        print("  prune: nothing to do (no sharded subdirectories in this publish)")
        return 0
    try:
        files = _retry("list_repo_files", lambda: api.list_repo_files(repo, repo_type="dataset"))
    except Exception as exc:  # noqa: BLE001 — best-effort, same as the upload path
        print(f"  ! prune: could not list {repo} ({exc}); skipping prune", file=sys.stderr)
        return 0
    # Only files prune can positively identify as one run's artifact are even considered. Anything
    # else in the scope — a shared intermediate, a future artifact kind this script does not know —
    # is left alone, because run-based bookkeeping cannot speak for it either way.
    candidates, skipped = {}, 0
    for f in files:
        sc = next((sc for sc in scopes if f.startswith(sc)), None)
        if sc is None or f.startswith(TRUTH_PREFIX):
            continue
        art = _run_artifact(f, sc)
        if art is None:
            skipped += 1
            continue
        candidates[f] = art
    # `superseded` bypasses the sharded-scope restriction because it does not rest on scope at all:
    # each of those paths was this run's own previous URL for a run whose replacement we just wrote.
    orphans = sorted((set(candidates) - uploaded - keep_extra) | set(superseded))
    for f in superseded:
        candidates.setdefault(f, (f.rsplit("__", 1)[0], "superseded"))
    extra = f", {skipped} shared/unrecognised file(s) not run artifacts (left alone)" if skipped else ""
    if superseded:
        print(f"  prune: {len(superseded)} file(s) superseded by this publish's own repointing")
    if not orphans:
        print(f"  prune: {len(candidates)} run artifact(s) in scope, none orphaned{extra}")
        return 0
    # Report by RUN, not by file count: "3 runs retired" is something you can check against what you
    # changed, where "1% of files" is not. Every deletion names the run it belonged to.
    by_run = {}
    for f in orphans:
        by_run.setdefault(candidates[f][0], []).append(candidates[f][1])
    print(f"  prune: {len(orphans)} orphaned artifact(s) across {len(by_run)} run(s) "
          f"of {len(candidates)} in scope{extra}")
    for rid in sorted(by_run)[:10]:
        print(f"      - {rid}: {', '.join(sorted(by_run[rid]))}")
    if len(by_run) > 10:
        print(f"      … and {len(by_run) - 10} more run(s)")
    if dry_run:
        print("  prune: --prune-dry-run, deleting nothing")
        return 0
    deleted = 0
    for start in range(0, len(orphans), BATCH):
        chunk = orphans[start:start + BATCH]
        ops = [_delete_op(f) for f in chunk]
        desc = f"prune batch {start // BATCH + 1}/{(len(orphans) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=ops, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=o,
                commit_message=f"prune orphaned volumes ({d})"))
            deleted += len(chunk)
            print(f"  ✓ {desc} ({deleted}/{len(orphans)})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {desc} failed: {exc}", file=sys.stderr)
    return deleted


FLAT_COVERAGE_MIN = 0.5


def flat_orphans(files, known_ids: set, live_paths: set) -> tuple[list, float]:
    """Flat-root run artifacts belonging to no run in `known_ids`, and how much of the flat root the
    supplied indexes explain.

    This is the one deletion in this file that rests on ABSENCE — a retired or renamed run leaves its
    volumes behind and there is no positive record that it did. That makes the completeness of
    `known_ids` load-bearing, and the flat root is shared by every non-repro track, so a single index
    is not enough: pass every index that references the repo.

    The returned coverage is the share of flat-root artifacts that DO belong to a known run. It is a
    precondition on the input, not a cap on the output — the distinction that matters, because a
    "refuse if deleting more than half" rule reads a correct large cleanup and a catastrophic one
    identically, while low coverage means precisely "the index list I was given does not describe
    this repo".
    """
    known = set(known_ids) | {i.replace("~", "_").replace("+", "_") for i in known_ids}
    orphans, live = [], 0
    for f in files:
        if "/" in f or f.startswith(TRUTH_PREFIX):
            continue
        art = _run_artifact(f, "")
        if art is None:
            continue                      # not a per-run artifact: the same rule as the sharded prune
        if art[0] in known or f in live_paths:
            live += 1
        else:
            orphans.append(f)
    total = live + len(orphans)
    return sorted(orphans), (live / total if total else 1.0)


def _repo_path(url: str, repo: str) -> "str | None":
    """The in-repo path a download URL points at, or None if it is not this repo's URL."""
    base = _url(repo, "")
    return url[len(base):].split("?")[0] if isinstance(url, str) and url.startswith(base) else None


def _prune_flat(api, repo, rows: list, extra_indexes: list, dry_run: bool) -> int:
    """Remove flat-root volumes belonging to runs no index knows about (retired or renamed methods).

    Separate from the sharded prune because the flat root is shared by every non-repro track, so the
    results dir driving this publish is never the whole picture. Requires `--index` for the other
    indexes and refuses when they explain too little of what is there.
    """
    known = {r.get("id") for r in rows if r.get("id")}
    live = _indexed_paths(rows, repo)
    for idx in extra_indexes:
        if not idx.exists():
            print(f"! prune-flat: {idx} does not exist — refusing to judge with an index list I "
                  f"cannot read.", file=sys.stderr)
            return 0
        other = json.loads(idx.read_text())
        other_rows = other["runs"] if isinstance(other, dict) else other
        known |= {r.get("id") for r in other_rows if r.get("id")}
        live |= _indexed_paths(other_rows, repo)
    try:
        files = _retry("list_repo_files", lambda: api.list_repo_files(repo, repo_type="dataset"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! prune-flat: could not list {repo} ({exc}); skipping", file=sys.stderr)
        return 0
    orphans, coverage = flat_orphans(files, known, live)
    print(f"  prune-flat: {len(known)} run id(s) across {1 + len(extra_indexes)} index file(s) "
          f"explain {coverage:.0%} of the flat root")
    if coverage < FLAT_COVERAGE_MIN:
        print(f"  ! prune-flat: refusing — those indexes explain only {coverage:.0%} of the flat "
              f"root, so the list is incomplete and live runs would look retired. Pass every index "
              f"that references {repo} with --index.", file=sys.stderr)
        return 0
    if not orphans:
        print("  prune-flat: nothing orphaned")
        return 0
    by_run: dict = {}
    for f in orphans:
        by_run.setdefault(f.rsplit("__", 1)[0], []).append(f.rsplit("__", 1)[1])
    print(f"  prune-flat: {len(orphans)} file(s) across {len(by_run)} retired run(s)")
    for rid in sorted(by_run)[:10]:
        print(f"      - {rid}: {', '.join(sorted(by_run[rid]))}")
    if len(by_run) > 10:
        print(f"      … and {len(by_run) - 10} more run(s)")
    if dry_run:
        print("  prune-flat: --prune-dry-run, deleting nothing")
        return 0
    deleted = 0
    for start in range(0, len(orphans), BATCH):
        chunk = orphans[start:start + BATCH]
        desc = f"prune-flat batch {start // BATCH + 1}"
        try:
            _retry(desc, lambda o=chunk, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=[_delete_op(f) for f in o],
                commit_message=f"prune volumes of retired runs ({d})"))
            deleted += len(chunk)
            print(f"  ✓ {desc} ({deleted}/{len(orphans)})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {desc} failed: {exc}", file=sys.stderr)
    return deleted


def _indexed_paths(rows: list, repo: str) -> set:
    """Repo paths that the index already points at — live volumes this publish may not have
    re-uploaded (published by an earlier job, or no longer on this machine's disk)."""
    prefix = f"https://huggingface.co/datasets/{repo}/resolve/main/"
    keep = set()
    for r in rows:
        urls = list((r.get("volumes") or {}).values())
        for k in ("resources_url", "regions_url"):
            if r.get(k):
                urls.append(r[k])
        for u in urls:
            if isinstance(u, str) and u.startswith(prefix):
                keep.add(u[len(prefix):])
    return keep


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
        args = [a for a in args if a != str(runs_file)]     # the --runs value is not the results dir
    prune, prune_dry = _prune_flags(sys.argv)
    prune_flat = "--prune-flat" in sys.argv
    extra_indexes = _extra_indexes(sys.argv)
    args = [a for a in args if a not in {str(x) for x in extra_indexes}]
    results = Path(args[0]) if args else ROOT / "results"

    # Pruning from a shard would delete every OTHER shard's volumes: a --runs publish knows only
    # its own slice, so everything else in the scope looks orphaned. Only the index-mode publish
    # sees the complete picture.
    if prune and runs_file is not None:
        print("! --prune is not supported with --runs: a shard publish cannot tell an orphan from "
              "another shard's volume. Run a full index-mode publish to prune.", file=sys.stderr)
        return 1

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

    # Files THIS publish just replaced for a run it holds: the row pointed at path X for some kind,
    # it now points at Y, so X is superseded. The shared-ground-truth migration creates one of these
    # per run it moves (`<rid>__truth.nii.gz` -> `truth/<phantom>/<artifact>.nii.gz`), and since
    # publishing is an upsert the old copy would otherwise sit on the Hub forever with nothing able
    # to attribute it — the flat root is outside every sharded prune scope. Captured here because
    # this is the last moment the previous URL exists, and it is the strongest attribution available:
    # we know the run, the artifact, and that we wrote its replacement in this same run.
    superseded: set[str] = set()
    for rid, kinds in want.items():
        old_vols = by_id[rid].get("volumes") or {}
        for kind, url in old_vols.items():
            if kind not in kinds:
                continue                       # no replacement written this run — leave it alone
            path = _repo_path(url, repo)
            if path and "/" not in path and _url(repo, path) != kinds[kind]:
                superseded.add(path)

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

    if prune:
        # Two preconditions, both about whether this publish saw a COMPLETE picture — because prune
        # infers "retired" from absence, and an incomplete view makes live runs look retired.
        if failed:
            print("! prune: skipped — some uploads failed this run, so the produced set is "
                  "incomplete and anything missing would look orphaned.", file=sys.stderr)
        elif published < 0.9 * len(rows):
            print(f"! prune: skipped — this results directory produced volumes for {published} of "
                  f"{len(rows)} indexed runs. That is a partial publish, and every run missing from "
                  f"it would be read as retired. Publish from a complete results dir to prune.",
                  file=sys.stderr)
        else:
            scopes = {n[:n.rindex("/") + 1] for n in uploads if "/" in n}
            _prune(api, repo, set(landed), _indexed_paths(rows, repo), scopes, prune_dry,
                   superseded - _indexed_paths(rows, repo))
            if prune_flat:
                _prune_flat(api, repo, rows, extra_indexes, prune_dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
