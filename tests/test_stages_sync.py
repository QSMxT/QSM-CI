"""Drift guard: the two hand-maintained plain-Python copies of the stage table — qsm_ci/stages.py
(so the installed CLI needs no YAML dep) and scripts/pipeline.py (the standalone scorer) — must
both mirror the authoritative stages.yml.

When they disagree, the scorer and the CLI mount/accept different inputs: e.g. pipeline.py once kept
`magnitude` under `dipole` while qsm_ci dropped it, so the scorer passed `--magnitude` to a `qsm-ci
run` that rejected it and every dipole method DNF'd. These tests fail the PR instead — update the
drifted copy to match stages.yml.
"""
import importlib.util
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


def _load_pipeline():
    spec = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_stages_match_yaml():
    assert pystages.STAGES == _EXPECTED_STAGES, (
        "qsm_ci/stages.py STAGES drifted from stages.yml (stages + spans) — update it to match."
    )


def test_cli_artifact_files_match_yaml():
    assert pystages.ARTIFACT_FILE == _EXPECTED_FILES, (
        "qsm_ci/stages.py ARTIFACT_FILE drifted from stages.yml artifacts.*.file — update it."
    )


def test_scorer_stages_match_yaml():
    pipeline = _load_pipeline()
    assert pipeline.STAGES == _EXPECTED_STAGES, (
        "scripts/pipeline.py STAGES drifted from stages.yml — update it (this is what made every "
        "dipole method DNF when the CLI and scorer disagreed on --magnitude)."
    )
    assert pipeline.ARTIFACT_FILE == _EXPECTED_FILES, (
        "scripts/pipeline.py ARTIFACT_FILE drifted from stages.yml artifacts.*.file — update it."
    )
