"""The Julia-original submissions share one piece of glue, qsmci_io.jl.

Each submission folder is mounted on its own at /algo, so every Julia submission carries a copy of
algorithms/_julia/qsmci_io.jl. This keeps the copies identical, so a fix lands in all of them.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "algorithms" / "_julia" / "qsmci_io.jl"
COPIES = sorted((ROOT / "algorithms").glob("*/qsmci_io.jl"))


@pytest.mark.parametrize("copy", [c for c in COPIES if c != CANONICAL], ids=lambda p: p.parent.name)
def test_qsmci_io_copy_is_identical(copy):
    assert copy.read_bytes() == CANONICAL.read_bytes(), (
        f"{copy.parent.name}/qsmci_io.jl differs from algorithms/_julia/qsmci_io.jl; "
        "edit the canonical file and copy it to every Julia submission"
    )


JULIA = sorted(p.parent.name for p in (ROOT / "algorithms").glob("*/qsmci_io.jl")
               if p.parent.name != "_julia")


def test_julia_originals_are_parity_only():
    """The Julia originals are port parity references only (docs/parity.md): never scored, never in
    the site manifest; the PR smoke gate still runs them."""
    import json
    import sys
    import yaml
    sys.path.insert(0, str(ROOT / "scripts"))
    import pipeline
    import score_plan
    assert len(JULIA) == 12, JULIA
    for slug in JULIA:
        spec = yaml.safe_load((ROOT / "algorithms" / slug / "algorithm.yml").read_text())
        assert spec.get("parity_only") is True, slug
        assert score_plan.is_skipped(spec), slug
    scored = {a["slug"] for a in pipeline.discover_algorithms()}
    assert not scored & set(JULIA)
    assert {a["slug"] for a in pipeline.discover_algorithms(include={"tkd-qsmjl"})} >= {"tkd-qsmjl"}
    site = {a["slug"] for a in json.loads((ROOT / "web" / "algorithms.json").read_text())["algorithms"]}
    assert not site & set(JULIA)
