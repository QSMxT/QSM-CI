"""Guard: every submission appears in the generated web/algorithms.json manifest.

The site fetches web/algorithms.json to render each method's card (name, description,
parameters, DOI) on the leaderboard + submission pages. It is a generated file
(scripts/gen_manifest.py). Keeping the *committed* copy in sync is no longer a manual
chore — the `manifest` job in .github/workflows/ci.yml regenerates it and commits the
refresh back to the branch on same-repo pushes/PRs (fork PRs, which CI can't push to,
must run `python scripts/gen_manifest.py` and commit). This test just pins that no
submission is missing from the manifest the generator builds.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_manifest", ROOT / "scripts" / "gen_manifest.py")
gen_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_manifest)


def test_every_submission_is_in_the_manifest():
    import yaml

    manifest = {a["slug"] for a in gen_manifest.build()["algorithms"]}
    for d in sorted((ROOT / "algorithms").glob("*/")):
        yml = d / "algorithm.yml"
        if d.name.startswith("_") or not yml.exists():
            continue
        slug = (yaml.safe_load(yml.read_text()) or {}).get("slug") or d.name
        assert slug in manifest, f"submission {d.name} (slug {slug}) missing from manifest"
