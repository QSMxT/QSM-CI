"""Unit test for the evaluate.yml execution-relevance filter (scripts/ci_eval_targets.py).

The important, testable logic is the pure `execution_relevant(base_doc, head_doc)` decision — the git
plumbing around it is exercised in CI itself. A metadata-only edit must be skipped; any change to a
run-relevant field (or a new/unparseable method) must be smoked.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ci_eval_targets", Path(__file__).resolve().parent.parent / "scripts" / "ci_eval_targets.py")
cet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cet)

BASE = {"name": "TKD", "slug": "tkd", "stage": "dipole", "image": "ghcr.io/x/tkd:1",
        "parameters": [{"name": "thr", "default": 0.19}]}


def test_metadata_only_edit_is_not_relevant():
    head = {**BASE, "language": "Python", "family": "direct", "description": "now with more words",
            "doi": "10.1/x", "engine": "Independent"}
    assert cet.execution_relevant(BASE, head) is False


def test_param_change_is_relevant():
    head = {**BASE, "parameters": [{"name": "thr", "default": 0.25}]}
    assert cet.execution_relevant(BASE, head) is True


def test_stage_and_image_changes_are_relevant():
    assert cet.execution_relevant(BASE, {**BASE, "stage": "bfr+dipole"}) is True
    assert cet.execution_relevant(BASE, {**BASE, "image": "ghcr.io/x/tkd:2"}) is True


def test_new_or_unparseable_method_is_relevant():
    assert cet.execution_relevant(None, BASE) is True      # new method (no base)
    assert cet.execution_relevant(BASE, None) is True      # head unparseable → fail safe


def test_identical_docs_not_relevant():
    assert cet.execution_relevant(BASE, dict(BASE)) is False


def test_docs_files_are_not_execution_relevant():
    # A BUILD.md/README.md edit is the one non-yml change that cannot alter how a method runs.
    assert cet.is_docs("BUILD.md") is True
    assert cet.is_docs("README.md") is True
    assert cet.is_docs("notes/DESIGN.MD") is True
    for f in ("run.sh", "Dockerfile", "recon.py", "recon.m", "weights.onnx", "config.json", "README.md.sh"):
        assert cet.is_docs(f) is False, f


def test_fidelity_record_and_site_fields_are_not_relevant():
    # Re-recording the container's fidelity check, or a website-only field, must not re-smoke.
    head = {**BASE, "fidelity": {"date": "2026-11-03", "tolerance": "identical"}, "hidden": True,
            "qsmxt_value": "tkd", "qsmxt_args": ["--x"]}
    assert cet.execution_relevant(BASE, head) is False


def test_smoke_runs_on_the_methods_scoring_tier():
    # Unset runner: hosted, like its scoring; self-hosted/highmem/manual methods stay self-hosted.
    root = Path(__file__).resolve().parent.parent / "algorithms"
    tiers = {p.parent.name: (__import__("yaml").safe_load(p.read_text()) or {}).get("runner")
             for p in root.glob("*/algorithm.yml") if not p.parent.name.startswith("_")}
    unset = next(s for s, r in sorted(tiers.items()) if r is None)
    selfhosted = next(s for s, r in sorted(tiers.items()) if r in ("self-hosted", "highmem", "manual"))
    m = {t["slug"]: t for t in cet.matrix([unset, selfhosted])}
    assert m[unset] == {"slug": unset, "hosted": True, "runs_on": "ubuntu-latest"}
    assert m[selfhosted]["hosted"] is False
    assert m[selfhosted]["runs_on"] == ["self-hosted", "Linux", "X64"]
