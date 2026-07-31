#!/usr/bin/env python3
"""Build web/algorithms.json from every algorithms/<slug>/algorithm.yml.

The submission page fetches this manifest to show what each algorithm is — description, parameters,
citation/DOI, source, and any `ci_notes` — and the leaderboard uses it to badge methods that carry
notes on how QSM-CI runs them.
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


def _inputs(meta: dict) -> list:
    """The artifacts this method actually reads (its declared `inputs:`, else the stage's consumes) —
    so the site's 'run it yourself' command lists only the flags the method uses. Empty for a method
    whose stage isn't a known pipeline stage."""
    return _consumes(meta) if meta.get("stage") in STAGES else []


def entry(meta: dict) -> dict:
    authors = meta.get("authors") or []
    author_names = [a.get("name") if isinstance(a, dict) else a for a in authors]
    return {
        "slug": meta["slug"],
        "name": meta.get("name", meta["slug"]),
        "stage": meta.get("stage"),
        # The artifacts this method actually consumes (declared `inputs:` ∩ stage, else the full stage
        # consumes) — the viewer's "run it yourself" command lists only these flags.
        "inputs": _inputs(meta),
        # Leaderboard / submission-sidebar domain: 'qsm' (the field-mapping→bfr→dipole pipeline) or
        # 'chisep' (susceptibility source separation). Explicit `domain:` wins; else derived from stage.
        "domain": meta.get("domain") or ("chisep" if meta.get("stage") == "chi-separation" else "qsm"),
        "engine": meta.get("engine"),
        # Taxonomy axes (controlled vocabularies), used by the site's figures — e.g. the findings
        # runtime chart's colour selector. Value sets are documented in scripts/apply_metadata.py.
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
    }


def build() -> dict:
    algos = []
    for d in sorted((ROOT / "algorithms").glob("*/")):
        mfile = d / "algorithm.yml"
        if d.name.startswith("_") or not mfile.exists():
            continue
        meta = yaml.safe_load(mfile.read_text())
        meta.setdefault("slug", d.name)
        algos.append(entry(meta))
    return {"algorithms": algos}


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def main() -> None:
    manifest = build()
    out = ROOT / "web" / "algorithms.json"
    out.write_text(render(manifest))
    print(f"wrote {out} ({len(manifest['algorithms'])} algorithms)")


if __name__ == "__main__":
    main()
