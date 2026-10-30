#!/usr/bin/env python3
"""Build web/algorithms.json from every algorithms/<slug>/algorithm.yml.

The submission page fetches this manifest to show what each algorithm is — description, parameters,
citation/DOI, source, and any `ci_notes` — and the leaderboard uses it to badge methods that carry
notes on how QSM-CI runs them.

It also embeds the dataset/phantom registry (scripts/datasets.json) as a `datasets` block, so the
site can label runs by the phantom they were scored on (run rows carry a `phantom` field; absence
means the track's default phantom) and offer per-phantom filtering where a track has several.

And the harmonization cohorts (scripts/repro_format.py REPRO_GROUPS) as a `repro_groups` list, in
display order: each cohort's site dataset key, tab label and payload paths, so the site shows one
Harmonization dataset per cohort, each reading only its own payloads.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qsm_ci.runner import _consumes  # noqa: E402
from qsm_ci.stages import STAGES  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from repro_format import REPRO_GROUPS, group_of, payload_names  # noqa: E402


def _inputs(meta: dict) -> list:
    """The artifacts this method actually reads (its declared `inputs:`, else the stage's consumes
    plus any `optional_inputs:`) — so the site's 'run it yourself' command lists only the flags the
    method uses. Empty for a method whose stage isn't a known pipeline stage."""
    return _consumes(meta) if meta.get("stage") in STAGES else []


def entry(meta: dict) -> dict:
    authors = meta.get("authors") or []
    author_names = [a.get("name") if isinstance(a, dict) else a for a in authors]
    return {
        "slug": meta["slug"],
        "name": meta.get("name", meta["slug"]),
        "stage": meta.get("stage"),
        # The artifacts this method actually consumes — runner._consumes, so a declared `inputs:`
        # naming something outside the stage contract (MEDI's magnitude) is carried through, not
        # dropped. The viewer's "run it yourself" command lists exactly these flags.
        "inputs": _inputs(meta),
        # Leaderboard / submission-sidebar domain: 'qsm' (the field-mapping→bfr→dipole pipeline) or
        # 'chisep' (susceptibility source separation; R2′ generators live there too — they only run
        # on chisep-track phantoms). Explicit `domain:` wins; else derived from stage.
        "domain": meta.get("domain") or ("chisep" if meta.get("stage") in ("chi-separation", "r2prime-generation") else "qsm"),
        "engine": meta.get("engine"),
        # The method's algorithm name, and how QSMxT names it: the viewer builds the equivalent
        # `qsmxt run` command from these (web/js/qsmxtCommand.js), never from the QSM-CI slug.
        # `qsmxt_value` overrides `algorithm` where the CLI value differs; `qsmxt_args` adds the
        # flags `qsmxt run` needs to match how QSM-CI runs the method. Both emitted only when set.
        "algorithm": meta.get("algorithm"),
        **({"qsmxt_value": meta["qsmxt_value"]} if meta.get("qsmxt_value") else {}),
        **({"qsmxt_args": list(meta["qsmxt_args"])} if meta.get("qsmxt_args") else {}),
        # Taxonomy axes (controlled vocabularies), used by the site's figures — e.g. the findings
        # runtime chart's colour selector. Value sets are documented in scripts/oneoff/apply_metadata.py.
        "language": meta.get("language"),   # Rust | MATLAB | Python
        "family": meta.get("family"),       # direct | iterative | deep-learning | bayesian
        "learning": meta.get("learning"),   # none | pretrained | untrained
        "description": (meta.get("description") or "").strip(),
        "citation": meta.get("citation"),
        "doi": meta.get("doi"),
        "code_url": meta.get("code_url"),
        "license": meta.get("license"),
        "authors": author_names,
        # `parameters:` is the canonical key; tolerate a stray `params:` so a mistyped
        # submission still shows its parameter rows instead of silently dropping them.
        "parameters": meta.get("parameters") or meta.get("params") or [],
        # Optional notes on how QSM-CI runs this method vs. its reference (e.g. CPU-only execution of
        # a GPU method, model complexity reduced to fit the runner) — shown on the submission page.
        "ci_notes": meta.get("ci_notes") or [],
        # `hidden: true` retires a submission from the RESULTS surfaces (leaderboard/viewer) while its
        # stored rows stay in index.json — the web drops any run whose stage is a hidden method
        # (web/js/app.js loadRuns). Emitted only when set so the manifest diff stays minimal.
        **({"hidden": True} if meta.get("hidden") else {}),
    }


# Submission well-formedness rules, enforced HERE (at authoring time, since every submission PR
# regenerates the manifest) as well as in CI. Keep in sync with tests/test_submissions.py.
REQUIRED_FIELDS = ("name", "slug", "stage", "image", "run")
# Sources that carry a codebase reimplementation of a generic technique — tagged into the slug
# (algorithm[-variant]-source). Branded/unique published methods (any other source) stay bare.
_TAGGED_SOURCES = {"qsmrs", "sti", "cornell", "qsmci"}


def _valid_stages() -> set:
    stages_yml = yaml.safe_load((ROOT / "stages.yml").read_text())
    return set(stages_yml.get("stages", {})) | set(stages_yml.get("spans", {}))


def validate(d: Path, meta: dict, valid_stages: set) -> None:
    """Fail fast, with the same messages the CI gate (tests/test_submissions.py) would produce —
    so a malformed algorithm.yml is caught on the author's machine, not after push."""
    problems = []
    for field in REQUIRED_FIELDS:
        if not meta.get(field):
            problems.append(f"missing required field '{field}'")
    if meta.get("stage") and meta["stage"] not in valid_stages:
        problems.append(f"unknown stage {meta['stage']!r} (valid: {sorted(valid_stages)})")
    if meta.get("slug") and meta["slug"] != d.name:
        problems.append(f"slug {meta['slug']!r} must equal the directory name {d.name!r}")
    algorithm, source, variant = meta.get("algorithm"), meta.get("source"), meta.get("variant")
    if not (algorithm and source):
        problems.append("needs 'algorithm' and 'source' fields")
    else:
        parts = [algorithm] + ([variant] if variant else []) + ([source] if source in _TAGGED_SOURCES else [])
        derived = "-".join(parts)
        if meta.get("slug") != derived:
            problems.append(
                f"slug {meta.get('slug')!r} != derived {derived!r} "
                f"(algorithm={algorithm}, variant={variant}, source={source}; "
                f"tagged sources {sorted(_TAGGED_SOURCES)} get the -source suffix, branded ones stay bare)")
    if problems:
        sys.exit(f"gen_manifest: {d.name}/algorithm.yml is malformed:\n  - " + "\n  - ".join(problems))


def build() -> dict:
    algos = []
    valid_stages = _valid_stages()
    for d in sorted((ROOT / "algorithms").glob("*/")):
        mfile = d / "algorithm.yml"
        if d.name.startswith("_") or not mfile.exists():
            continue
        meta = yaml.safe_load(mfile.read_text())
        validate(d, meta, valid_stages)
        # A parity_only original is never scored and has no results: it is a port parity reference
        # (docs/parity.md), not a method on the site.
        if meta.get("parity_only"):
            continue
        meta.setdefault("slug", d.name)
        algos.append(entry(meta))
    # The dataset/phantom registry, verbatim — the web needs the label/track/default fields to name
    # phantoms and pick each track's default (a run row without a `phantom` field is the default).
    datasets = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    return {"algorithms": algos, "datasets": datasets, "repro_groups": repro_groups(datasets)}


def repro_groups(datasets: dict) -> list:
    """The harmonization cohorts that have acquisitions in the registry, in REPRO_GROUPS order:
    [{id, key, label, description, repro, regions}] (payload paths relative to the site root)."""
    used = {group_of(v) for v in datasets.values() if v.get("track") == "repro"}
    unknown = sorted(used - set(REPRO_GROUPS))
    if unknown:
        sys.exit(f"gen_manifest: scripts/datasets.json names harmonization group(s) {unknown} that "
                 "scripts/repro_format.py REPRO_GROUPS does not define")
    out = []
    for gid, g in REPRO_GROUPS.items():
        if gid not in used:
            continue
        names = payload_names(gid)
        out.append({"id": gid, "key": g["key"], "label": g["label"], "description": g["description"],
                    "repro": "results/" + names["repro"], "regions": "results/" + names["regions"]})
    return out


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def main() -> None:
    manifest = build()
    out = ROOT / "web" / "algorithms.json"
    out.write_text(render(manifest))
    print(f"wrote {out} ({len(manifest['algorithms'])} algorithms)")


if __name__ == "__main__":
    main()
