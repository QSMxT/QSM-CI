#!/usr/bin/env python3
"""Decide which changed submissions actually need a smoke re-run in evaluate.yml.

The per-PR `evaluate` gate runs each *changed* method in its container. But "changed" must mean
"changed in a way that affects how it RUNS" — not a metadata-only edit. A pure taxonomy/description
touch to every algorithm.yml (as the metadata backfill did) otherwise re-smokes the whole method
zoo for hours, testing nothing.

A slug needs a smoke run iff, relative to the base ref, either:
  - a non-`algorithm.yml`, non-documentation file under algorithms/<slug>/ changed (run.sh,
    Dockerfile, weights, config, recon.py, …) — a `.md` edit (BUILD.md, README.md) cannot change
    how the method runs, so it is ignored, or
  - `algorithm.yml` changed in any field OUTSIDE the cosmetic-metadata allowlist below (stage,
    image, inputs, produces, parameters, smoke_box, … — anything that changes execution), or
  - the method is new (no algorithm.yml at the base).

Output: a compact JSON array of slugs to stdout, e.g. `["tkd-qsmrs","sharp-qsmrs"]` — ready for a matrix.

    python scripts/ci_eval_targets.py --base origin/main

Fails SAFE: any parse/git error on a candidate includes it (better a needless smoke than a missed
broken run.sh).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import yaml

# Keys on algorithm.yml that are DISPLAY/PROVENANCE only — editing them cannot change how the method
# runs, so a diff confined to these does not warrant a smoke run. Everything else (stage, slug, image,
# inputs, optional_inputs, produces, parameters, smoke_box, run, …) is treated as execution-relevant.
COSMETIC_KEYS = {
    "name", "language", "family", "learning", "engine", "description", "citation", "doi",
    "authors", "license", "code_url", "domain", "ci_notes", "tags", "notes", "references", "tuned",
    "tuning", "algorithm", "variant", "source",
    # Records and site-only fields: `fidelity` is the container-vs-licensed-original check's record,
    # `hidden`/`qsmxt_value`/`qsmxt_args` only feed the website (gen_manifest.py). Re-recording a
    # fidelity check must not re-smoke (or, via score_plan.py, rescore) the method.
    "fidelity", "hidden", "qsmxt_value", "qsmxt_args",
}


def is_docs(relpath: str) -> bool:
    """A documentation file under a method folder. The container mounts the whole folder, but no
    run.sh/recon.* reads a .md, so editing one cannot change execution — a BUILD.md path fix must not
    cost a smoke run (qsmart-matlab's 32³ smoke crop DNFs on its own, unrelated to the docs edit)."""
    return relpath.lower().endswith(".md")


def execution_relevant(base_doc: "dict | None", head_doc: "dict | None") -> bool:
    """True if the two algorithm.yml docs differ once cosmetic-only keys are stripped. A new method
    (base_doc is None) or an unparseable doc is always relevant."""
    if base_doc is None or head_doc is None:
        return True
    strip = lambda d: {k: v for k, v in d.items() if k not in COSMETIC_KEYS}
    return strip(base_doc) != strip(head_doc)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def _load(text: str) -> "dict | None":
    try:
        doc = yaml.safe_load(text)
        return doc if isinstance(doc, dict) else None
    except yaml.YAMLError:
        return None


def targets(base: str) -> list[str]:
    changed = [p for p in _git("diff", "--name-only", f"{base}...").splitlines()
               if p.startswith("algorithms/")]
    # slug -> set of changed relative paths under it
    by_slug: dict[str, set[str]] = {}
    for p in changed:
        parts = p.split("/")
        if len(parts) < 3 or parts[1].startswith("_"):
            continue  # not algorithms/<slug>/<file>, or a shared _base
        by_slug.setdefault(parts[1], set()).add("/".join(parts[2:]))

    out: list[str] = []
    for slug, files in sorted(by_slug.items()):
        spec = f"algorithms/{slug}/algorithm.yml"
        # A deleted submission (or a non-submission file under algorithms/) has no head algorithm.yml
        # and can't be evaluated — drop it rather than failing on it.
        head_exists = subprocess.run(["git", "cat-file", "-e", f"HEAD:{spec}"],
                                     capture_output=True).returncode == 0
        if not head_exists:
            continue
        # A method may opt out of CI runs entirely with `ci_skip: true` (e.g. it needs a runner tier
        # QSM-CI doesn't have yet — DIP-UP is GPU-only). Never smoke it; discover_algorithms() skips it
        # too, so a smoke job would only DNF the runner. Flipping ci_skip back to false is itself a
        # non-cosmetic yml change, so re-enabling picks the method back up on the next diff.
        head_doc = _load(_git("show", f"HEAD:{spec}"))
        if isinstance(head_doc, dict) and head_doc.get("ci_skip"):
            continue
        # Any non-yml, non-docs change under the method → execution could differ → smoke it.
        if any(f != "algorithm.yml" and not is_docs(f) for f in files):
            out.append(slug)
            continue
        # Only algorithm.yml and/or docs changed: compare base vs head algorithm.yml with cosmetic
        # keys stripped (a docs-only change leaves them identical → not relevant).
        base_yaml = _git("show", f"{base}:{spec}")
        head_yaml = _git("show", f"HEAD:{spec}")
        if execution_relevant(_load(base_yaml) if base_yaml else None, _load(head_yaml)):
            out.append(slug)
    return out


# The smoke runs on the runner tier the method is scored on (`runner:` in algorithm.yml, read by
# score_plan.py): unset/hosted/hosted-large on GitHub's hosted runners, self-hosted/highmem/manual
# on QSM-CI's self-hosted ones. A method that scores on hosted runners fits on one, and its smoke (a
# small crop) does too; keeping it off the two shared self-hosted runners stops a long main-branch
# scoring run from queueing every PR's smoke behind it. highmem smokes on self-hosted rather than on
# the QSMCI_HIGHMEM_RUNNER pool: the crop needs none of its memory and that pool is lent.
HOSTED_TIERS = {"hosted", "hosted-large"}


def matrix(slugs: list[str]) -> list[dict]:
    """The evaluate matrix: each slug with the runner its smoke runs on."""
    from pathlib import Path
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import score_plan  # imports this module; imported here to keep the import one-way at load time
    root = here.parent / "algorithms"
    out = []
    for slug in slugs:
        spec = score_plan.load_spec(root, slug)
        tier = str(score_plan._scalar((spec or {}).get("runner")) or "")
        hosted = score_plan.TIERS.get(tier, "hosted") in HOSTED_TIERS
        out.append({"slug": slug, "hosted": hosted,
                    "runs_on": "ubuntu-latest" if hosted else ["self-hosted", "Linux", "X64"]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="base ref to diff against (e.g. origin/main)")
    ap.add_argument("--matrix", action="store_true",
                    help="emit [{slug, hosted, runs_on}] (evaluate.yml's matrix) instead of slugs")
    args = ap.parse_args()
    slugs = targets(args.base)
    print(json.dumps(matrix(slugs) if args.matrix else slugs, separators=(",", ":")))


if __name__ == "__main__":
    main()
