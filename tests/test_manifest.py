"""Drift guard: the committed web/algorithms.json must match algorithms/*/algorithm.yml.

The site fetches web/algorithms.json to render each method's card (name, description,
parameters, DOI) on the leaderboard + submission pages. It's a generated file
(scripts/gen_manifest.py) that nothing regenerates automatically, so it silently goes
stale when a submission is added or edited — a missing/incomplete method card is the
symptom. This test fails the PR instead: run `python scripts/gen_manifest.py` to refresh.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_manifest", ROOT / "scripts" / "gen_manifest.py")
gen_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_manifest)


def test_algorithms_manifest_is_current():
    committed = (ROOT / "web" / "algorithms.json").read_text()
    expected = gen_manifest.render(gen_manifest.build())
    assert committed == expected, (
        "web/algorithms.json is stale — run `python scripts/gen_manifest.py` and commit."
    )


def test_every_submission_is_in_the_manifest():
    import yaml

    manifest = {a["slug"] for a in gen_manifest.build()["algorithms"]}
    for d in sorted((ROOT / "algorithms").glob("*/")):
        yml = d / "algorithm.yml"
        if d.name.startswith("_") or not yml.exists():
            continue
        slug = (yaml.safe_load(yml.read_text()) or {}).get("slug") or d.name
        assert slug in manifest, f"submission {d.name} (slug {slug}) missing from manifest"
