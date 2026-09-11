"""Drift guard: the two hand-maintained plain-Python copies of the stage table — qsm_ci/stages.py
(so the installed CLI needs no YAML dep) and scripts/pipeline.py (the standalone scorer) — must
both mirror the authoritative stages.yml. So must the two human-facing copies, CONTRACT.md and
docs/submitting.md (their stage/artifact tables once stopped at brain-extraction/chimap while
stages.yml — and fourteen submissions — declared chi-separation, r2prime-generation and the
r2prime/chi-para/chi-dia artifacts; issue #221).

When they disagree, the scorer and the CLI mount/accept different inputs: e.g. pipeline.py once kept
`magnitude` under `dipole` while qsm_ci dropped it, so the scorer passed `--magnitude` to a `qsm-ci
run` that rejected it and every dipole method DNF'd. These tests fail the PR instead — update the
drifted copy to match stages.yml.
"""
import re
from pathlib import Path

import yaml

import qsm_ci.stages as pystages

ROOT = Path(__file__).resolve().parent.parent
_YML = yaml.safe_load((ROOT / "stages.yml").read_text())

_EXPECTED_STAGES = {
    name: {"consumes": spec["consumes"], "produces": spec["produces"]}
    for name, spec in {**_YML["stages"], **_YML["spans"]}.items()
}
_EXPECTED_FILES = {name: spec["file"] for name, spec in _YML["artifacts"].items() if "file" in spec}


def test_cli_stages_match_yaml():
    assert pystages.STAGES == _EXPECTED_STAGES, (
        "qsm_ci/stages.py STAGES drifted from stages.yml (stages + spans) — update it to match."
    )


def test_cli_artifact_files_match_yaml():
    assert pystages.ARTIFACT_FILE == _EXPECTED_FILES, (
        "qsm_ci/stages.py ARTIFACT_FILE drifted from stages.yml artifacts.*.file — update it."
    )


def test_scorer_stages_match_yaml(pipeline):
    assert pipeline.STAGES == _EXPECTED_STAGES, (
        "scripts/pipeline.py STAGES drifted from stages.yml — update it (this is what made every "
        "dipole method DNF when the CLI and scorer disagreed on --magnitude)."
    )
    assert pipeline.ARTIFACT_FILE == _EXPECTED_FILES, (
        "scripts/pipeline.py ARTIFACT_FILE drifted from stages.yml artifacts.*.file — update it."
    )


def _table_keys(md: Path, heading: str) -> set:
    """Backticked first-column names of every markdown table row in the section that starts at
    `heading` and ends at the next heading of any level (so `## Artifacts` stops before
    `### params.json`)."""
    text = md.read_text()
    m = re.search(rf"^{re.escape(heading)}\s*$(.*?)(?=^#{{1,6}} |\Z)", text, re.M | re.S)
    assert m, f"{md.name}: heading {heading!r} not found"
    lines = m.group(1).splitlines() + [""]
    keys = set()
    for line, nxt in zip(lines, lines[1:]):
        row = re.match(r"^\| `([^`]+)` \|", line)
        if row and not re.match(r"^\|\s*-", nxt):   # skip a header row (followed by |---|)
            keys.add(row.group(1))
    return keys


def test_contract_lists_every_stage_and_span():
    assert _table_keys(ROOT / "CONTRACT.md", "## Stages") == set(_EXPECTED_STAGES), (
        "CONTRACT.md's Stages/Spans tables drifted from stages.yml — add or remove the row."
    )


def test_contract_lists_every_artifact():
    assert _table_keys(ROOT / "CONTRACT.md", "## Artifacts") == set(_EXPECTED_FILES), (
        "CONTRACT.md's Artifacts table drifted from stages.yml artifacts — add or remove the row."
    )


def test_submitting_guide_lists_every_stage_and_span():
    assert _table_keys(ROOT / "docs" / "submitting.md", "## 1. Pick your stage") == set(_EXPECTED_STAGES), (
        "docs/submitting.md §1's stage table drifted from stages.yml — add or remove the row."
    )
