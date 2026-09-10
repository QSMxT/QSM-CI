"""`qsm-ci … --help` shows help, for every command — and `qsm-ci run <slug>` guidance is per-stage.

Two halves:

* The CLI's help routing (#225). `qsm-ci list --help` used to print the algorithm listing (the
  `list` shortcut in main() ran before argparse saw `--help`); `run` is a passthrough whose flags
  depend on the chosen method's stage, so `qsm-ci run --help` must say what you can run and
  `qsm-ci run <slug> --help` must show that method's own parser — including when an option comes
  before the slug, which argparse's REMAINDER cannot do (why main() dispatches `run` itself).

* The `qsm-ci run <slug>` inputs help + params echo: a ppm stage (BFR/dipole) must NOT ask for echo
  times / field strength (they don't enter the maths), must advertise the -o output flag, and its
  params echo must not imply TE/B0 were used. Field-mapping still requires echo times + field strength.
"""
import argparse
from pathlib import Path

import pytest

from qsm_ci import cli
from qsm_ci.runner import _inputs_summary, _params_summary

METHODS = Path(__file__).resolve().parent / "methods"


def _algo(stage, name="X"):
    return {"stage": stage, "name": name}


@pytest.fixture
def fixture_methods(monkeypatch):
    """Point slug resolution and `qsm-ci list` at tests/methods (cp-bfr, cp-method, …)."""
    monkeypatch.setenv("QSMCI_ALGORITHMS", str(METHODS))


def _help_exit(argv, capsys) -> str:
    """Run cli.main(argv), which argparse ends with SystemExit(0) for --help; return stdout."""
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0
    return capsys.readouterr().out


# ------------------------------------------------------------------------- CLI help routing


def test_top_level_help_lists_every_command(capsys):
    out = _help_exit(["--help"], capsys)
    for cmd in ("list", "new", "run", "submit", "interface", "doctor"):
        assert cmd in out


def test_module_docstring_names_every_subcommand():
    """The docstring is the CLI's summary; a subcommand missing from it (interface was) is invisible."""
    sub = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    for cmd in sub.choices:
        assert f"qsm-ci {cmd}" in cli.__doc__, f"`qsm-ci {cmd}` is not described in the module docstring"


def test_list_help_is_help_not_the_listing(fixture_methods, capsys):
    out = _help_exit(["list", "--help"], capsys)
    assert out.startswith("usage: qsm-ci list")
    assert "cp-method" not in out and "Available algorithms" not in out


def test_list_still_lists(fixture_methods, capsys):
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Available algorithms" in out and "cp-method" in out and "cp-bfr" in out
    assert "usage:" not in out


def test_run_help_without_a_slug_says_what_you_can_run(fixture_methods, capsys):
    for argv in (["run", "--help"], ["run", "-h"]):
        assert cli.main(argv) == 0
        out = capsys.readouterr().out
        assert "usage: qsm-ci run <slug>" in out
        assert "cp-method" in out   # the listing, so the next step is obvious


def test_run_slug_help_shows_that_methods_parser(fixture_methods, capsys):
    assert cli.main(["run", "cp-method", "--help"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: qsm-ci run cp-method")
    assert "--localfield" in out and "--mask" in out and "-o" in out   # a dipole's own inputs
    assert "--totalfield" not in out


def test_run_slug_help_works_with_an_option_before_the_slug(fixture_methods, capsys):
    """The passthrough must not choke on `qsm-ci run --runner local <slug> --help`."""
    assert cli.main(["run", "--runner", "local", "cp-bfr", "--help"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: qsm-ci run cp-bfr")
    assert "--totalfield" in out   # a bfr's input


def test_parser_run_entry_is_a_passthrough_to_run_command():
    """The `run` entry in build_parser() is not display-only: it takes the tail verbatim and its
    handler is the run dispatcher, so parse_args(["run", …]) and main(["run", …]) agree."""
    args = cli.build_parser().parse_args(["run", "cp-method", "--localfield", "lf.nii.gz", "-o", "x"])
    assert args.cmd == "run"
    assert args.args == ["cp-method", "--localfield", "lf.nii.gz", "-o", "x"]
    assert args.func is cli._cmd_run


# ------------------------------------------------------- per-stage `qsm-ci run <slug>` guidance


def test_dipole_help_is_ppm_aware_and_shows_output():
    h = _inputs_summary("ilsqr", _algo("dipole", "iLSQR"))
    assert "echo times / field strength aren't used" in h
    assert "--te" not in h and "--field-strength" not in h  # not offered for a ppm stage
    assert "-o PATH" in h and "chimap.nii.gz" in h          # output flag is discoverable
    assert "--localfield localfield.nii.gz --mask mask.nii.gz" in h  # bare run works


def test_field_mapping_help_requires_echo_and_b0():
    h = _inputs_summary("laplacian-fieldmap", _algo("field-mapping", "Laplacian"))
    assert "--te" in h and "[required here]" in h
    assert "--field-strength" in h
    assert "-o PATH" in h  # output flag shown for every stage


def test_params_summary_omits_unused_fields_for_ppm_stages():
    p = {"TE": [], "B0": 3.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}
    assert "TE / field strength not used by this stage" in _params_summary(p, "dipole")
    assert "TE=" not in _params_summary(p, "dipole")
    # field-mapping does use them, so they appear
    assert "TE=" in _params_summary(p, "field-mapping")
