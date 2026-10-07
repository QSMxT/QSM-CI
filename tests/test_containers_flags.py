"""qsm_ci/containers.py — GPU passthrough (Layer A off-by-default) and the QSMCI_* param env (Layer B).

Two small pieces of the container invocation that are easy to break invisibly. `_gpu_flags` must stay
OFF unless QSMCI_GPU is explicitly truthy, so CI on CPU-only hosts keeps producing byte-identical
commands, and each engine needs its OWN spelling of the flag (`--gpus all` is a docker-ism that
podman and apptainer reject). `_param_env` re-exports params.json and config.json as environment
variables purely so a run.sh need not parse JSON without `jq`; it is additive — the JSON files are
still written — so a malformed file must degrade to "no env vars" rather than fail the run.
`tests/test_containers.py` covers the user-mapping and runner probes in the same module.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from qsm_ci import containers
from qsm_ci.stages import ARTIFACT_FILE

RUNNERS = ["docker", "podman", "apptainer", "local"]


@pytest.fixture(autouse=True)
def _no_inherited_gpu_setting(monkeypatch):
    """A developer with QSMCI_GPU exported must not change what these tests mean."""
    monkeypatch.delenv("QSMCI_GPU", raising=False)


# --------------------------------------------------------------------------------- _gpu_flags


@pytest.mark.parametrize("runner", RUNNERS)
def test_no_gpu_flags_without_an_explicit_opt_in(runner):
    """The default is off: CI runs on CPU-only hosts and never sets QSMCI_GPU."""
    assert containers._gpu_flags(runner) == []


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " on ", "Yes"])
def test_a_truthy_opt_in_is_accepted_in_any_spelling(monkeypatch, value):
    monkeypatch.setenv("QSMCI_GPU", value)
    assert containers._gpu_flags("docker") == ["--gpus", "all"]


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "   ", "2", "enabled"])
def test_anything_else_leaves_the_gpu_alone(monkeypatch, value):
    """Only the documented truthy words count — an unrecognised value falls back to off rather than
    passing a flag the engine may not support."""
    monkeypatch.setenv("QSMCI_GPU", value)
    assert containers._gpu_flags("docker") == []


@pytest.mark.parametrize("runner,expected", [
    ("docker", ["--gpus", "all"]),
    ("podman", ["--device", "nvidia.com/gpu=all"]),
    ("apptainer", ["--nv"]),
    ("local", []),               # nothing to pass through: no container to pass it into
    ("singularity", []),
])
def test_each_runner_gets_its_own_spelling_of_the_flag(monkeypatch, runner, expected):
    monkeypatch.setenv("QSMCI_GPU", "1")
    assert containers._gpu_flags(runner) == expected


# -------------------------------------------------------------------------------- _param_env


def _params(tmp_path: Path, doc) -> Path:
    (tmp_path / ARTIFACT_FILE["params"]).write_text(doc if isinstance(doc, str) else json.dumps(doc))
    return tmp_path


def _config(tmp_path: Path, doc) -> Path:
    (tmp_path / "config.json").write_text(doc if isinstance(doc, str) else json.dumps(doc))
    return tmp_path


def test_an_empty_input_dir_exports_nothing(tmp_path):
    assert containers._param_env(tmp_path) == {}


def test_params_json_becomes_qsmci_env_vars(tmp_path):
    _params(tmp_path, {"TE": [0.004, 0.012, 0.02], "B0": 3.0,
                       "B0_dir": [0.0, 0.0, 1.0], "voxel_size": [1.0, 1.0, 1.0]})
    assert containers._param_env(tmp_path) == {
        "QSMCI_TE": "0.004 0.012 0.02",
        "QSMCI_TE0": "0.004",            # the common single-echo case, pre-split for run.sh
        "QSMCI_B0": "3.0",
        "QSMCI_B0_DIR": "0.0 0.0 1.0",
        "QSMCI_VOXEL_SIZE": "1.0 1.0 1.0",
    }


def test_a_list_is_space_separated_so_run_sh_can_iterate_it(tmp_path):
    """Shell-friendly on purpose: `for te in $QSMCI_TE` must enumerate the echoes."""
    _params(tmp_path, {"TE": [0.01, 0.02], "B0_dir": [0, 0, 1]})
    env = containers._param_env(tmp_path)
    assert env["QSMCI_TE"].split() == ["0.01", "0.02"]
    assert env["QSMCI_B0_DIR"].split() == ["0", "0", "1"]


def test_absent_and_empty_fields_are_simply_not_exported(tmp_path):
    """An empty TE must not become QSMCI_TE="" — run.sh tests these with -n/-z."""
    _params(tmp_path, {"TE": [], "B0_dir": [], "voxel_size": []})
    assert containers._param_env(tmp_path) == {}


def test_a_zero_field_strength_is_still_exported(tmp_path):
    """B0 is checked against None, not truthiness, so a legitimately zero value survives."""
    _params(tmp_path, {"B0": 0})
    assert containers._param_env(tmp_path) == {"QSMCI_B0": "0"}


def test_a_null_field_strength_is_not_exported(tmp_path):
    _params(tmp_path, {"B0": None})
    assert containers._param_env(tmp_path) == {}


def test_set_overrides_become_uppercase_qsmci_set_vars(tmp_path):
    _config(tmp_path, {"iterations": 200, "lambda": 0.05, "Verbose": True, "mode": "fast"})
    assert containers._param_env(tmp_path) == {
        "QSMCI_SET_ITERATIONS": "200",
        "QSMCI_SET_LAMBDA": "0.05",
        "QSMCI_SET_VERBOSE": "True",
        "QSMCI_SET_MODE": "fast",
    }


def test_params_and_overrides_are_exported_together(tmp_path):
    _params(tmp_path, {"B0": 7.0})
    _config(tmp_path, {"alpha": 1})
    assert containers._param_env(tmp_path) == {"QSMCI_B0": "7.0", "QSMCI_SET_ALPHA": "1"}


def test_an_unparseable_params_file_does_not_sink_the_run(tmp_path):
    """Layer B is additive — the JSON files are mounted anyway, so a bad read means "no env vars",
    not an exception out of _run_container."""
    _params(tmp_path, "{not json")
    _config(tmp_path, {"alpha": 1})
    assert containers._param_env(tmp_path) == {"QSMCI_SET_ALPHA": "1"}


def test_an_unparseable_config_file_does_not_sink_the_run(tmp_path):
    _params(tmp_path, {"B0": 3.0})
    _config(tmp_path, "[1, 2, 3]")   # valid JSON, but not a mapping of overrides
    assert containers._param_env(tmp_path) == {"QSMCI_B0": "3.0"}
