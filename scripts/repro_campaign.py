"""The harmonization matrix's campaign: scripts/repro_campaign.yml (see its header).

load() reads and checks it. derive() turns the discovered submissions into the campaign's matrix for
pipeline.py: the listed methods, plus each parity version as its own entry (the base submission with
a fixed `preset`, which run_algo passes like --set overrides), with a field-mapping variant's `chain`
attached. manifest_entries() gives gen_manifest.py the parity versions' web/algorithms.json entries.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = ROOT / "scripts" / "repro_campaign.yml"
CHAIN_KEYS = ("bfrs", "dipoles", "spans")


def _value(v) -> str:
    """A preset value as the --set string a wrapper's jq reads (true/false, not Python's True)."""
    return str(v).lower() if isinstance(v, bool) else str(v)


def load(path: Path = CAMPAIGN, algorithms: Path = ROOT / "algorithms") -> dict:
    """The campaign, checked: every method and variant base exists, every preset names a parameter
    the base declares, and a chain names only methods or variants of the campaign."""
    c = yaml.safe_load(path.read_text()) or {}
    methods = {s for slugs in (c.get("methods") or {}).values() for s in slugs}
    variants = c.get("variants") or {}
    problems = []

    def spec(slug):
        p = algorithms / slug / "algorithm.yml"
        return yaml.safe_load(p.read_text()) if p.exists() else None

    for s in sorted(methods):
        if spec(s) is None:
            problems.append(f"method {s}: no algorithms/{s}/algorithm.yml")
    for v, d in variants.items():
        base = d.get("base")
        if not base or v.split(".", 1)[0] != base or "." not in v:
            problems.append(f"variant {v}: must be named <base>.<tag> after its base")
            continue
        doc = spec(base)
        if doc is None:
            problems.append(f"variant {v}: base {base} does not exist")
            continue
        declared = {str(p.get("name")) for p in doc.get("parameters") or []}
        for k in d.get("set") or {}:
            if k not in declared:
                problems.append(f"variant {v}: {base} declares no parameter {k!r}")
        if not d.get("label"):
            problems.append(f"variant {v}: needs a label")
        chain = d.get("chain")
        if chain is not None:
            if doc.get("stage") != "field-mapping":
                problems.append(f"variant {v}: only a field-mapping variant takes a chain")
            for k, slugs in chain.items():
                if k not in CHAIN_KEYS:
                    problems.append(f"variant {v}: chain key {k!r} is not one of {CHAIN_KEYS}")
                for s in slugs or []:
                    if s not in methods and s not in variants:
                        problems.append(f"variant {v}: chain names {s}, not in the campaign")
        elif doc.get("stage") == "field-mapping":
            problems.append(f"variant {v}: a field-mapping variant needs a chain")
    for s in c.get("gpu") or []:
        if s not in methods:
            problems.append(f"gpu: {s} is not a campaign method")
    if problems:
        raise SystemExit(f"{path.name}:\n  - " + "\n  - ".join(problems))
    return c


def derive(algos: list[dict], campaign: dict, part: str = "all") -> list[dict]:
    """The matrix's submissions: the campaign's methods and parity versions, from the discovered
    `algos`. `part` cpu leaves out the gpu methods; gpu keeps the upstream stages and only the gpu
    dipoles (and no spans); all keeps everything."""
    by = {a["slug"]: a for a in algos}
    methods = {s for slugs in (campaign.get("methods") or {}).values() for s in slugs}
    gpu = set(campaign.get("gpu") or [])
    out = [by[s] for s in sorted(methods) if s in by]
    for v, d in (campaign.get("variants") or {}).items():
        base = by.get(d["base"])
        if base is None:
            continue
        a = {**base, "slug": v, "name": f"{base['name']} · {d['label']}",
             "preset": {k: _value(x) for k, x in (d.get("set") or {}).items()}}
        if d.get("chain") is not None:
            a["chain"] = {k: set(d["chain"].get(k) or []) for k in CHAIN_KEYS}
        out.append(a)
    if part == "cpu":
        out = [a for a in out if a["slug"] not in gpu]
    elif part == "gpu":
        # Only the upstreams the gpu dipoles invert: a `compose:` restriction names them, so the gpu
        # job does not recompute every background-removal column for nothing.
        dips = [a for a in out if a["slug"] in gpu]
        fms = set.union(*(a["compose"]["fieldmaps"] for a in dips)) if all(
            (a.get("compose") or {}).get("fieldmaps") for a in dips) else None
        bfrs = set.union(*(a["compose"]["bfrs"] for a in dips)) if all(
            (a.get("compose") or {}).get("bfrs") for a in dips) else None
        out = dips + [a for a in out
                      if ("totalfield" in a["produces"] and (fms is None or a["slug"] in fms))
                      or ("localfield" in a["produces"] and (bfrs is None or a["slug"] in bfrs))]
    return out


def manifest_entries(base_entries: dict, campaign: dict) -> list[dict]:
    """web/algorithms.json entries for the parity versions: the base's entry under the variant's slug
    and name, marked `variant_of` its base with the `preset` it runs and `repro_only`."""
    out = []
    for v, d in (campaign.get("variants") or {}).items():
        base = base_entries.get(d["base"])
        if base is None:
            continue
        out.append({**base, "slug": v, "name": f"{base['name']} · {d['label']}",
                    "variant_of": d["base"], "repro_only": True,
                    "preset": {k: _value(x) for k, x in (d.get("set") or {}).items()}})
    return out
