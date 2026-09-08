"""results/index.json agrees with the repository it describes.

Sixteen composed rows once carried pre-rename slugs (`bfrnet+fansi`) that disagreed with their own
id / combo (`gt~bfrnet~fansi-nltv-qsmrs-cmp`), so anything keyed by slug missed them; the registry
still offered two methods whose submission folders had been deleted. These pin the invariants.
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _submissions() -> set:
    out = set()
    for d in (ROOT / "algorithms").glob("*/"):
        yml = d / "algorithm.yml"
        if d.name.startswith("_") or not yml.exists():
            continue
        out.add((yaml.safe_load(yml.read_text()) or {}).get("slug") or d.name)
    return out


def test_composed_rows_name_the_methods_their_combo_names():
    runs = json.loads((ROOT / "results" / "index.json").read_text())["runs"]
    bad = []
    for r in runs:
        c = r.get("combo") or {}
        if r.get("mode") != "composed" or not c.get("dipole"):
            continue
        want = "+".join(x for x in (c.get("field_mapping"), c.get("bfr"), c.get("dipole")) if x and x != "gt")
        if r["slug"] != want:
            bad.append((r["id"], r["slug"], want))
    assert not bad, bad


def test_every_slug_atom_in_the_index_is_a_submission():
    runs = json.loads((ROOT / "results" / "index.json").read_text())["runs"]
    known = _submissions()
    unknown = sorted({a for r in runs for a in r["slug"].split("+")} - known)
    assert not unknown, f"index.json names methods with no submission folder: {unknown}"


def test_registry_only_lists_methods_that_exist():
    reg = json.loads((ROOT / "qsm_ci" / "registry.json").read_text())
    missing = sorted(set(reg) - _submissions())
    assert not missing, f"registry.json entries with no algorithms/<slug>/: {missing}"
