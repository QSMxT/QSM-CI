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


def test_gre_only_pairings_are_valid():
    """Every committed `gre_only:` pairing names a real R2′ generator and sits on a method that reads
    r2prime — build() would exit otherwise; this pins the specific checks."""
    gen = {"stage": "r2prime-generation"}
    ok = {"stage": "chi-separation", "inputs": ["localfield", "chimap", "r2prime", "mask"],
          "gre_only": {"generator": "gen", "name": "Method-R2*"}}
    assert gen_manifest.gre_only_problems({"gen": gen, "m": ok}) == []
    bad = {
        "unknown generator": {**ok, "gre_only": {"generator": "nope", "name": "x"}},
        "generator wrong stage": {**ok, "gre_only": {"generator": "m2", "name": "x"}},
        "no name": {**ok, "gre_only": {"generator": "gen"}},
        "gre-native method": {**ok, "inputs": ["magnitude", "chimap", "mask"]},
        "not chi-separation": {**ok, "stage": "dipole"},
        "unknown key": {**ok, "gre_only": {"generator": "gen", "name": "x", "extra": 1}},
    }
    m2 = {"stage": "chi-separation", "inputs": ["r2prime"]}
    for why, meta in bad.items():
        assert gen_manifest.gre_only_problems({"gen": gen, "m2": m2, "m": meta}), why
    pairs = {a["slug"]: a["gre_only"] for a in gen_manifest.build()["algorithms"] if a.get("gre_only")}
    assert pairs.get("chisepnet", {}).get("generator") == "r2primenet"
