"""The `qsm-ci run <slug>` inputs help + params echo: correct per-stage guidance.

A ppm stage (BFR/dipole) must NOT ask for echo times / field strength (they don't enter the
maths), must advertise the -o output flag, and its params echo must not imply TE/B0 were used.
Field-mapping still requires echo times + field strength.
"""
import types

from qsm_ci.runner import _inputs_summary, _params_summary


def _algo(stage, name="X"):
    return {"stage": stage, "name": name}


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
