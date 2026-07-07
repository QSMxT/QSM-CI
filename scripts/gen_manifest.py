#!/usr/bin/env python3
"""Build web/algorithms.json from every algorithms/<slug>/metadata.yml.

The site (Methods page + submission page) fetches this manifest to show what each algorithm is —
description, parameters, citation/DOI, source — alongside the scores. Normalises the two metadata
shapes (generated QSMxT ones and hand-written ones).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def entry(meta: dict) -> dict:
    authors = meta.get("authors") or []
    author_names = [a.get("name") if isinstance(a, dict) else a for a in authors]
    return {
        "slug": meta["slug"],
        "name": meta.get("name", meta["slug"]),
        "stage": meta.get("stage"),
        "engine": meta.get("engine"),
        "description": (meta.get("description") or "").strip(),
        "citation": meta.get("citation"),
        "doi": meta.get("doi") or meta.get("paper_doi"),
        "code_url": meta.get("code_url"),
        "license": meta.get("license"),
        "authors": author_names,
        "parameters": meta.get("parameters") or [],
    }


def main() -> None:
    algos = []
    for d in sorted((ROOT / "algorithms").glob("*/")):
        mfile = d / "metadata.yml"
        if d.name.startswith("_") or not mfile.exists():
            continue
        meta = yaml.safe_load(mfile.read_text())
        meta.setdefault("slug", d.name)
        algos.append(entry(meta))
    out = ROOT / "web" / "algorithms.json"
    out.write_text(json.dumps({"algorithms": algos}, indent=2) + "\n")
    print(f"wrote {out} ({len(algos)} algorithms)")


if __name__ == "__main__":
    main()
