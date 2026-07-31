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
