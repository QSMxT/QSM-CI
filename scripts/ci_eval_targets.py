#!/usr/bin/env python3
"""Decide which changed submissions actually need a smoke re-run in evaluate.yml.

The per-PR `evaluate` gate runs each *changed* method in its container. But "changed" must mean
"changed in a way that affects how it RUNS" — not a metadata-only edit. A pure taxonomy/description
touch to every algorithm.yml (as the metadata backfill did) otherwise re-smokes the whole method
zoo for hours, testing nothing.

A slug needs a smoke run iff, relative to the base ref, either:
  - a non-`algorithm.yml` file under algorithms/<slug>/ changed (run.sh, Dockerfile, weights,
    config, recon.py, …), or
  - `algorithm.yml` changed in any field OUTSIDE the cosmetic-metadata allowlist below (stage,
    image, inputs, produces, parameters, smoke_box, … — anything that changes execution), or
  - the method is new (no algorithm.yml at the base).

Output: a compact JSON array of slugs to stdout, e.g. `["tkd","sharp"]` — ready for a matrix.

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
}


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
        # Any non-yml change under the method → execution could differ → smoke it.
        if any(f != "algorithm.yml" for f in files):
            out.append(slug)
            continue
        # Only algorithm.yml changed: compare base vs head with cosmetic keys stripped.
        base_yaml = _git("show", f"{base}:{spec}")
        head_yaml = _git("show", f"HEAD:{spec}")
        if execution_relevant(_load(base_yaml) if base_yaml else None, _load(head_yaml)):
            out.append(slug)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="base ref to diff against (e.g. origin/main)")
    args = ap.parse_args()
    print(json.dumps(targets(args.base)))


if __name__ == "__main__":
    main()
