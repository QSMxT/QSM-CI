"""Drift guard: qsm_ci/stages.py must mirror the authoritative stages.yml.

qsm_ci/stages.py is a hand-maintained plain-Python copy of stages.yml (so the installed CLI needs
no YAML dependency and no repo checkout). When they disagree, the CLI advertises inputs the scorer
doesn't provide — e.g. dipole once listed `magnitude` in stages.py but not stages.yml, so every
dipole method's `qsm-ci run` help implied a magnitude file it never uses. This test fails the PR
instead: update qsm_ci/stages.py to match stages.yml.
"""
from pathlib import Path

import yaml

import qsm_ci.stages as pystages

ROOT = Path(__file__).resolve().parent.parent
_YML = yaml.safe_load((ROOT / "stages.yml").read_text())


def test_stages_match_yaml():
    expected = {
        name: {"consumes": spec["consumes"], "produces": spec["produces"]}
        for name, spec in {**_YML["stages"], **_YML["spans"]}.items()
    }
    assert pystages.STAGES == expected, (
        "qsm_ci/stages.py STAGES drifted from stages.yml (stages + spans) — update it to match."
    )


def test_artifact_files_match_yaml():
    expected = {
        name: spec["file"] for name, spec in _YML["artifacts"].items() if "file" in spec
    }
    assert pystages.ARTIFACT_FILE == expected, (
        "qsm_ci/stages.py ARTIFACT_FILE drifted from stages.yml artifacts.*.file — update it."
    )
