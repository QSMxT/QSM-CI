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
but a URL is only recorded once its file has landed (or an earlier copy is known to be there — see
below), so index.json never points at a file the Hub does not hold.

Layout. The Hub rejects a whole commit once any directory in the repo holds more than 10,000 files
(HF_DIR_CAP), so a full directory does not fail one file — it fails every file in the batch, on every
publish, until something is deleted. That is what happened to the flat root in September 2026: two
rescores lost ~250 in-silico runs' viewer volumes to "too many files per directory". Per-run
artifacts therefore never go in the root. Repro runs live under `repro/<acquisition>/` (the viewer
builds those URLs from that pattern); every other run under `runs/<phantom>/<hh>/`, `<hh>` being the
first two hex digits of sha1(run id) — 256 buckets per phantom, so no realistic matrix gets near the
cap. The root still holds the per-run files published before sharding. Rows keep pointing at them
until a rescore republishes the run into its bucket, and a `--prune` publish then deletes the flat
copy as superseded.

Best-effort: a batch that fails after a few retries is skipped, never aborting the publish — the
leaderboard scores live in index.json (committed by the workflow regardless). A circuit breaker
bails out early if the Hub is genuinely down, so we never grind for hours. A run whose upload did not
land keeps its viewer where it can: if the Hub already holds an earlier publish of that artifact (at
the same path, or at its pre-sharding flat path) the row points there and is flagged
`volumes_stale`, which the viewer discloses. Only a run with no earlier copy at all loses its URLs,
and those are listed in publish-incomplete.json. `--relink` applies the same recovery to an index
after the fact, without uploading anything.

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
  python scripts/publish_volumes.py --relink                   # no upload: point scored rows that
                                                              # lost their URLs back at copies the
                                                              # Hub already holds (see _relink)
  python scripts/publish_volumes.py --prune-repro [--prune-dry-run]
                                                              # harmonization track: delete every
                                                              # repro/<acq>/ file no live pipeline
                                                              # can name (see _prune_repro)

`--prune` (index mode only; score.yml's merge job passes it) is the automated housekeeping, and it
never deletes a file that is the only copy a row points at. Two kinds of deletion, on different
evidence:

  * REPLACED — positive attribution: this publish landed a run artifact whose previous copy sat at
    another path (the pre-sharding flat copy, or a per-run truth the shared truth replaced). The old
    path is deleted on every publish, partial or not, because we know its replacement is there.
  * RETIRED — absence: a run artifact in a bucket this publish wrote to that no row in index.json
    references and this publish did not produce (a method dropped from the matrix, a renamed id).
    Only after a publish whose every upload landed, so a failure can never be read as retirement.

The harmonization track is judged differently, because it is addressed differently: results/repro.json
names every live pipeline (repro_eval.py drops methods retired from the manifest), and the viewer
derives every URL from pipeline id × acquisition — recon and sidecars per pipeline, a total field per
field-mapping method, a local field per (field-mapping, bfr) pair, a magnitude per acquisition. So
`--prune-repro` (repro.yml's evaluate job) rebuilds that exact name set, under the acquisitions
scripts/datasets.json knows, and judges what falls outside it by the manifest, the way
repro_eval.drop_retired does: a file naming a method web/algorithms.json no longer defines is
RETIRED and deleted; one built only from live methods is merely UNHARVESTED — a GPU method whose
runs were published but never got ROI stats, a parked submission — and is kept, because it is the
only copy of that output and becomes reachable the moment a stats pass runs. An acquisition
directory the registry does not know is reported and left alone, and a pipeline list that explains
too little of what is there is refused as not describing the repo (FLAT_COVERAGE_MIN).

A run whose latest upload failed keeps pointing at its earlier copy (`volumes_stale`), and
`_indexed_paths` exempts everything a row points at from both kinds, so that copy survives until a
later publish lands the replacement — at which point it is REPLACED and goes. Deleting a path does
not free its storage on the Hub (git keeps the old LFS object until the history is squashed), so
score.yml squashes after every full rescore. See `_prune` and `_prune_flat`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from functools import lru_cache
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
# The Hub rejects any commit that would leave a directory holding more than this many files.
HF_DIR_CAP = 10_000
RUNS_PREFIX = "runs/"      # every non-repro run: runs/<phantom>/<hh>/<rid>__<kind>.<ext> (see _subdir)
SHARD_HEX = 2              # <hh> = this many leading hex digits of sha1(run id): 16**2 = 256 buckets


def _name(rid: str, kind: str, ext: str = "nii.gz", sub: str = "") -> str:
    # `sub` is the run's shard directory (see _subdir) and already a clean path; only the id part
    # needs the ~/+ sanitising. sub="" gives the flat-root name runs were published under before
    # sharding, which _earlier_copies still looks for.
    return sub + f"{rid}__{kind}.{ext}".replace("~", "_").replace("+", "_")


def _subdir(row: dict) -> str:
    """Repo subdirectory for a run's volumes — never the root, which is what hit HF_DIR_CAP.

    Repro runs shard by acquisition: `repro/<acq>/`, a pattern web/js/viewer.js builds URLs from, so
    it must not change. Every other run goes to `runs/<phantom>/<hh>/`, bucketed by a hash of the run
    id so the bucket is derivable from the id alone and fills evenly however the matrix grows. The
    phantom defaults the same way truth_name's does (historical sim rows carry none)."""
    if row.get("track") == "repro" and row.get("phantom"):
        return f"repro/{row['phantom']}/"
    phantom = row.get("phantom") or row.get("track") or "sim"
    bucket = hashlib.sha1(row["id"].encode()).hexdigest()[:SHARD_HEX]
    return f"{RUNS_PREFIX}{phantom}/{bucket}/"


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

    `scopes` drives the absence-based (RETIRED) deletions; the call site passes none after a partial
    publish, so a failed upload can never be read as retirement. `superseded` (REPLACED) is judged
    on its own evidence and is deleted either way — the call site has already removed anything a
    row still points at, which is what keeps a `volumes_stale` fallback copy alive.
    """
    scopes = {s for s in scopes if s and not s.startswith(TRUTH_PREFIX)}
    if not scopes and not superseded:
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
    # each of those paths was this run's own previous URL (or pre-sharding flat copy) for a run whose
    # replacement we just wrote. Only the ones actually on the Hub: deleting a missing path would
    # fail the whole prune commit.
    superseded = set(superseded) & set(files)
    orphans = sorted((set(candidates) - uploaded - keep_extra) | superseded)
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
    return _delete_batches(api, repo, orphans, "prune")


FLAT_COVERAGE_MIN = 0.5


@lru_cache(maxsize=1)
def live_algo_slugs() -> frozenset:
    """Method slugs web/algorithms.json still defines. Empty when the manifest is absent, which makes
    the corroboration silently unavailable rather than wrongly claiming everything is retired."""
    manifest = ROOT / "web" / "algorithms.json"
    if not manifest.exists():
        return frozenset()
    return frozenset(a["slug"] for a in json.loads(manifest.read_text()).get("algorithms", [])
                     if a.get("slug"))


def _leading_slug(rid: str) -> str:
    """The method slug a run id starts with — everything before the first -iso/-cmp marker."""
    for marker in ("-cmp", "-iso"):
        if marker in rid:
            return rid.split(marker)[0]
    return rid


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


def _annotate(msg: str) -> None:
    """Surface a problem where CI actually shows it — an annotation on the run, not just stderr."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error title=Incomplete volume publish::{msg}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as fh:
                fh.write(f"\n> **Incomplete volume publish** — {msg}\n")
    print(f"! {msg}", file=sys.stderr)


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
    # Corroboration, not a gate. "No index mentions it" is an absence; "and its method is not in the
    # manifest either" is a second, independent reason to believe the run is gone — which is what
    # separates a genuinely retired generation of runs from an index list that is merely incomplete.
    # Not a gate because a run may be retired while its method lives on (a rescore under a new id).
    slugs = live_algo_slugs()
    retired_slug = sum(1 for rid in by_run if _leading_slug(rid) not in slugs) if slugs else 0
    if by_run and slugs:
        print(f"      {retired_slug}/{len(by_run)} of them name a method the manifest no longer "
              f"defines ({100 * retired_slug / len(by_run):.0f}%)")
    for rid in sorted(by_run)[:10]:
        print(f"      - {rid}: {', '.join(sorted(by_run[rid]))}")
    if len(by_run) > 10:
        print(f"      … and {len(by_run) - 10} more run(s)")
    if dry_run:
        print("  prune-flat: --prune-dry-run, deleting nothing")
        return 0
    return _delete_batches(api, repo, orphans, "prune-flat")


def _delete_batches(api, repo, paths: list, what: str) -> int:
    """Delete `paths` in BATCH-sized commits, best-effort per batch (like uploads). Returns how many went."""
    deleted = 0
    for start in range(0, len(paths), BATCH):
        chunk = paths[start:start + BATCH]
        desc = f"{what} batch {start // BATCH + 1}/{(len(paths) + BATCH - 1) // BATCH}"
        try:
            _retry(desc, lambda o=chunk, d=desc: api.create_commit(
                repo, repo_type="dataset", operations=[_delete_op(f) for f in o],
                commit_message=f"{what}: delete {len(o)} file(s) ({d})"))
            deleted += len(chunk)
            print(f"  ✓ {desc} ({deleted}/{len(paths)})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {desc} failed: {exc}", file=sys.stderr)
    return deleted


# ── Harmonization (repro) track ──────────────────────────────────────────────────────────────────
# Nothing here is addressed by a URL in an index: the viewer derives every harmonization URL from a
# pipeline id and an acquisition (web/js/viewer.js reproReconUrl & co.), and results/repro.json is the
# list of live pipelines. Liveness is therefore DERIVED, the same way, and must stay byte-identical
# to those derivations — a drift here deletes live files (the 621-intermediate near-miss of 2026-09).
REPRO_PREFIX = "repro/"
REPRO_RUN_KINDS = (("recon", "nii.gz"), ("resources", "json"), ("regions", "json"))  # per pipeline×acq
REPRO_SHARED_KINDS = ("totalfield", "localfield", "magnitude")                       # per column / acq
REPRO_KINDS = frozenset(k for k, _ in REPRO_RUN_KINDS) | frozenset(REPRO_SHARED_KINDS)


def repro_acq_ids() -> frozenset:
    """Harmonization acquisition ids: the repro-track keys of scripts/datasets.json, the registry
    repro_eval.py and the site both read."""
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    return frozenset(k for k, v in reg.items() if v.get("track") == "repro")


def repro_live_names(pipelines, acqs) -> set:
    """Every Hub path the harmonization viewer can ask for, for these pipelines × acquisitions.

    Mirrors viewer.js exactly: `repro/<acq>/<pipe with + → _>-cmp-<acq>__{recon,resources,regions}`,
    `<fm>__totalfield` for any pipeline with an upstream field-mapping stage (2- and 3-part ids),
    `<fm>_<bfr>__localfield` for a full 3-part pipeline, and `<acq>__magnitude` per acquisition."""
    live = set()
    for acq in acqs:
        d = f"{REPRO_PREFIX}{acq}/"
        live.add(f"{d}{acq}__magnitude.nii.gz")
        for p in pipelines:
            parts = p.split("+")
            rid = p.replace("+", "_") + f"-cmp-{acq}"
            for kind, ext in REPRO_RUN_KINDS:
                live.add(f"{d}{rid}__{kind}.{ext}")
            if len(parts) >= 2:
                live.add(f"{d}{parts[0]}__totalfield.nii.gz")
            if len(parts) == 3:
                live.add(f"{d}{parts[0]}_{parts[1]}__localfield.nii.gz")
    return live


def repro_orphans(files, live: set, acqs, live_slugs) -> tuple[list, list, float, set]:
    """(retired, unharvested, coverage, unknown acquisition dirs) among the harmonization files.

    Judged: files directly under `repro/<acq>/` for a KNOWN acquisition whose kind is one this track
    publishes. Anything else — a kind this script does not know, a file without the `__kind` marker,
    a directory not in the registry — is left alone and (for directories) reported: deleting a whole
    acquisition should be a deliberate act, not a side effect of a registry edit.

    A judged file no live pipeline can name is RETIRED only if it names a method outside
    `live_slugs` (the manifest) — the rule repro_eval.drop_retired applies to pipelines. Otherwise it
    is UNHARVESTED: every method in it is live, only the ROI stats/fits that would put it in repro.json
    are missing (a GPU method run without a stats pass, a parked submission). Those are kept; they
    are the only copy. Methods are read off the name as `_`-separated slugs, which is unambiguous
    while no slug contains `_` (the caller checks). Coverage is the share of judged files repro.json
    explains: a precondition on the INPUT (see flat_orphans), not a cap on the output."""
    retired, unharvested, kept, unknown = [], [], 0, set()
    for f in files:
        if not f.startswith(REPRO_PREFIX):
            continue
        rest = f[len(REPRO_PREFIX):]
        if "/" not in rest:
            continue
        acq, base = rest.split("/", 1)
        if "/" in base or "__" not in base:
            continue
        if acq not in acqs:
            unknown.add(acq)
            continue
        stem, tail = base.rsplit("__", 1)
        if tail.split(".", 1)[0] not in REPRO_KINDS:
            continue
        if f in live:
            kept += 1
            continue
        methods = stem[: -len(f"-cmp-{acq}")] if stem.endswith(f"-cmp-{acq}") else stem
        (unharvested if all(m in live_slugs for m in methods.split("_")) else retired).append(f)
    total = kept + len(retired) + len(unharvested)
    return sorted(retired), sorted(unharvested), (kept / total if total else 1.0), unknown


def _prune_repro(api, repo, repro_json: Path, acqs, dry_run: bool) -> int:
    """--prune-repro: delete harmonization volumes no live pipeline can name. Returns the count."""
    if not repro_json.exists():
        print(f"! prune-repro: {repro_json} does not exist", file=sys.stderr)
        return 0
    pipelines = sorted(json.loads(repro_json.read_text()).get("pipelines") or {})
    if not pipelines:
        print("! prune-repro: repro.json names no pipelines — refusing to treat that as 'everything "
              "is retired'.", file=sys.stderr)
        return 0
    slugs = live_algo_slugs()
    if not slugs:
        print("! prune-repro: web/algorithms.json names no methods — cannot tell retired from "
              "unharvested; refusing.", file=sys.stderr)
        return 0
    if any("_" in s for s in slugs):
        print(f"! prune-repro: a method slug contains '_' ({[s for s in slugs if '_' in s]}), so "
              f"methods cannot be read off a file name unambiguously; refusing.", file=sys.stderr)
        return 0
    try:
        files = _retry("list_repo_files", lambda: api.list_repo_files(repo, repo_type="dataset"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! prune-repro: could not list {repo} ({exc}); skipping", file=sys.stderr)
        return 0
    live = repro_live_names(pipelines, acqs)
    orphans, unharvested, coverage, unknown = repro_orphans(files, live, acqs, slugs)
    print(f"  prune-repro: {len(pipelines)} live pipeline(s) × {len(acqs)} acquisition(s) explain "
          f"{coverage:.0%} of the harmonization files")
    if unharvested:
        by_u: dict = {}
        for f in unharvested:
            by_u.setdefault(f.rsplit("/", 1)[1].rsplit("__", 1)[0].split("-cmp-")[0], []).append(f)
        print(f"  prune-repro: {len(unharvested)} file(s) across {len(by_u)} pipeline/column(s) are "
              f"built only from live methods but absent from repro.json (no ROI stats yet, or parked) "
              f"— kept, they are the only copy")
        for k in sorted(by_u)[:5]:
            print(f"      - {k}: {len(by_u[k])} file(s)")
        if len(by_u) > 5:
            print(f"      … and {len(by_u) - 5} more")
    if unknown:
        print(f"  prune-repro: {len(unknown)} acquisition dir(s) not in scripts/datasets.json, left "
              f"alone: {', '.join(sorted(unknown))}")
    if coverage < FLAT_COVERAGE_MIN:
        print(f"  ! prune-repro: refusing — the pipeline list explains only {coverage:.0%} of what is "
              f"there, so it does not describe this repo (a broken harvest?).", file=sys.stderr)
        return 0
    if not orphans:
        print("  prune-repro: nothing orphaned")
        return 0
    by_pipe: dict = {}
    for f in orphans:
        by_pipe.setdefault(f.rsplit("/", 1)[1].rsplit("__", 1)[0].split("-cmp-")[0], []).append(f)
    print(f"  prune-repro: {len(orphans)} file(s) across {len(by_pipe)} retired pipeline/column(s) "
          f"(each names a method the manifest no longer defines)")
    for k in sorted(by_pipe)[:10]:
        print(f"      - {k}: {len(by_pipe[k])} file(s)")
    if len(by_pipe) > 10:
        print(f"      … and {len(by_pipe) - 10} more")
    if dry_run:
        print("  prune-repro: --prune-dry-run, deleting nothing")
        return 0
    return _delete_batches(api, repo, orphans, "prune-repro")


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


# Per-run artifacts a scored row can carry, for --relink. The "-dia" pair is χ-separation's χ− set.
RUN_KINDS = (("recon", "nii.gz"), ("error", "nii.gz"), ("resources", "json"), ("regions", "json"))
DIA_KINDS = (("recon-dia", "nii.gz"), ("error-dia", "nii.gz"))
SIDECARS = ("resources", "regions")   # JSON sidecars: top-level `<kind>_url`, not under `volumes`


def _is_chisep(row: dict) -> bool:
    """Whether a run writes the χ− "-dia" set — the viewer's isChisepRun rule. A bare R2′ generator
    shares the chisep domain but produces one map."""
    return ((row.get("domain") == "chisep" or row.get("stage") == "chi-separation")
            and row.get("stage") != "r2prime-generation")


def _earlier_copies(name: str) -> tuple:
    """Hub paths that may hold an earlier publish of the artifact at `name`, in order of preference:
    the path itself (the same run published there before), then — for a bucketed run artifact — the
    flat-root path it was published under before sharding."""
    return (name, name.rsplit("/", 1)[-1]) if name.startswith(RUNS_PREFIX) else (name,)


def fallback_urls(missing, existing: set, repo: str) -> dict:
    """{rid: {kind: url}} for each (rid, kind, name) in `missing` that has an earlier copy among the
    Hub's `existing` paths. Anything with no copy is left out: no URL beats a URL that 404s."""
    out: dict = {}
    for rid, kind, name in missing:
        hit = next((p for p in _earlier_copies(name) if p in existing), None)
        if hit:
            out.setdefault(rid, {})[kind] = _url(repo, hit)
    return out


def _has_url(row: dict, kind: str) -> bool:
    return bool(row.get(f"{kind}_url") if kind in SIDECARS else (row.get("volumes") or {}).get(kind))


def relink_urls(rows: list, existing: set, repo: str) -> dict:
    """What --relink would restore: for every SCORED row, each per-run artifact it has no URL for
    but the Hub holds a copy of. DNF rows are skipped — an earlier success's recon must never be
    shown for a run that failed. Ground truth is not touched: it is shared, and always recorded."""
    missing = []
    for row in rows:
        if row.get("status") != "ok":
            continue
        for kind, ext in RUN_KINDS + (DIA_KINDS if _is_chisep(row) else ()):
            if not _has_url(row, kind):
                missing.append((row["id"], kind, _name(row["id"], kind, ext, _subdir(row))))
    return fallback_urls(missing, existing, repo)


def _apply_urls(row: dict, kinds: dict, replace: bool) -> None:
    """Record {kind: url} on a row: the JSON sidecars as top-level `<kind>_url` (the viewer graphs
    resources and fetches regions), the NIfTIs under `volumes`. `replace` swaps the whole `volumes`
    map (a publish states what the run has now); otherwise the new kinds are merged in."""
    kinds = dict(kinds)
    for k in SIDECARS:
        url = kinds.pop(k, None)
        if url:
            row[f"{k}_url"] = url
    if kinds:
        row["volumes"] = kinds if replace else {**(row.get("volumes") or {}), **kinds}


def _relink(index: Path, repo: str, token) -> int:
    """--relink: point scored rows that lost their volume URLs back at copies already on the Hub.

    The recovery a partial publish needs after the fact — e.g. the September 2026 rescores, whose
    rejected batches left ~200 runs' files on the Hub but their URLs out of index.json. Uploads
    nothing and needs no write token (the volumes repo is public). Relinked rows are flagged
    `volumes_stale`: the copy is from an earlier publish than the metrics beside it, and the next
    successful publish of the run clears the flag."""
    from huggingface_hub import HfApi
    doc = json.loads(index.read_text())
    rows = doc["runs"] if isinstance(doc, dict) else doc
    try:
        existing = set(_retry("list_repo_files", lambda: HfApi(token=token).list_repo_files(
            repo, repo_type="dataset")))
    except Exception as exc:  # noqa: BLE001
        print(f"! could not list {repo} ({exc})", file=sys.stderr)
        return 1
    found = relink_urls(rows, existing, repo)
    by_id = {r["id"]: r for r in rows}
    for rid, kinds in found.items():
        _apply_urls(by_id[rid], kinds, replace=False)
        by_id[rid]["volumes_stale"] = True
    index.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"relinked {len(found)} run(s) to copies already on {repo} (flagged volumes_stale)")
    bare = sorted(r["id"] for r in rows
                  if r.get("status") == "ok" and not (r.get("volumes") or {}).get("recon"))
    if bare:
        print(f"! {len(bare)} scored run(s) still have no reconstruction anywhere on the Hub — only "
              f"a rescore that publishes them can fix these:", file=sys.stderr)
        for rid in bare:
            print(f"    {rid}", file=sys.stderr)
    return 0


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
    relink = "--relink" in sys.argv
    if not repo or not (token or relink):          # --relink only reads the (public) repo
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
    if relink:
        if runs_file is not None or prune:
            print("! --relink works on results/index.json alone; drop --runs/--prune", file=sys.stderr)
            return 1
        return _relink(results / "index.json", repo, token)
    if "--prune-repro" in sys.argv:
        if runs_file is not None or "--prune" in sys.argv:
            print("! --prune-repro stands alone (with --prune-dry-run at most)", file=sys.stderr)
            return 1
        _prune_repro(HfApi(token=token), repo, results / "repro.json", repro_acq_ids(), prune_dry)
        return 0

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
    # The same attribution for the move out of the flat root, which the loop above cannot see when
    # the row arrives without its old URLs (score.yml's merge replaces each rescored row wholesale):
    # a run artifact that just landed in its bucket supersedes the flat copy of the same name.
    # _prune only deletes those that actually exist.
    superseded |= {name.rsplit("/", 1)[-1] for _, _, name in refs
                   if name in landed and name.startswith(RUNS_PREFIX)}

    # A run whose upload did not land keeps its viewer if the Hub still holds an earlier publish of
    # the artifact. Before this, the row lost the URL outright while the file sat on the Hub, working
    # and unreferenced — how two rescores in September 2026 blanked ~250 runs' viewers.
    fallback: dict[str, dict[str, str]] = {}
    if failed:
        try:
            existing = set(_retry("list_repo_files", lambda: api.list_repo_files(
                repo, repo_type="dataset")))
        except Exception as exc:  # noqa: BLE001 — without a listing, no fallback; still report
            print(f"  ! could not list {repo} to find earlier copies ({exc})", file=sys.stderr)
            existing = set()
        fallback = fallback_urls([ref for ref in refs if ref[2] not in landed], existing, repo)
        for rid, kinds in fallback.items():
            want.setdefault(rid, {}).update(kinds)

    published = 0
    for rid, kinds in want.items():
        _apply_urls(by_id[rid], kinds, replace=True)
        if rid in fallback:
            by_id[rid]["volumes_stale"] = True     # disclosed by the viewer; see _relink
        else:
            by_id[rid].pop("volumes_stale", None)  # everything it points at is this publish's
        published += 1

    # Write the URLs back into whichever file sourced the ids: the central index.json (dict), or the
    # per-job runs-JSON (bare list) whose rows we patched in place via by_id.
    payload = doc if is_index else rows
    target.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"published volumes for {published} runs -> {target}")

    if prune:
        # Everything a row points at is exempt — computed AFTER the URLs above were written, so a
        # `volumes_stale` fallback copy counts as live and survives (see the module docstring).
        live = _indexed_paths(rows, repo)
        if failed:
            # REPLACED copies still go (their replacement demonstrably landed); RETIRED is judged by
            # absence, and after a failed upload absence proves nothing — so no scopes this time.
            print("! prune: some uploads failed, so only files this publish demonstrably replaced "
                  "are deleted; retired-run cleanup waits for a clean publish.", file=sys.stderr)
            scopes = set()
        else:
            # Liveness comes from the full index (`live`), not from what this results dir produced,
            # so a focused rescore may prune the buckets it touched: a file there that no row
            # references and this publish did not write belongs to no run any more.
            scopes = {n[:n.rindex("/") + 1] for n in uploads if "/" in n}
        _prune(api, repo, set(landed), live, scopes, prune_dry, superseded - live)
        if prune_flat and not failed:
            _prune_flat(api, repo, rows, extra_indexes, prune_dry)

    if failed:
        # Committing the index without these runs' URLs is deliberate — losing a whole rescore
        # because the Hub was briefly down would be worse. What was wrong is that it happened
        # SILENTLY: rc=0 under `continue-on-error: true` is a green job whose only trace is a `!`
        # line in a log nobody reads, and nothing retries short of another full rescore. On a
        # 47-batch publish one failed batch is ~1,000 runs quietly missing their volumes.
        missing = sorted({rid for rid, kind, name in refs
                          if name not in landed and kind not in fallback.get(rid, {})})
        stale = sorted(fallback)
        _annotate(f"{failed} volume file(s) failed to upload; {len(stale)} run(s) kept an earlier "
                  f"copy already on the Hub (flagged volumes_stale) and {len(missing)} run(s) have "
                  f"no copy at all — both need a re-publish")
        (target.parent / "publish-incomplete.json").write_text(json.dumps(
            {"failed_files": failed, "runs": missing, "stale_runs": stale}, indent=2) + "\n")
        print(f"! {len(missing)} run(s) left without volume URLs, {len(stale)} on stale copies — "
              f"listed in {target.parent / 'publish-incomplete.json'}", file=sys.stderr)
        return 2                      # distinct from 1 (hard error): index written, volumes partial
    return 0


if __name__ == "__main__":
    sys.exit(main())
