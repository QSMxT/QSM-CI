"""Guard: what the CLI says an input is must match what the method's code actually does.

Two failures motivated this, both hit on real BIDS data:

1. A glob written to catch the echoes (`--phase .../*part-phase*`) also sweeps in the BIDS JSON
   sidecars sitting beside them. Those travelled all the way down to nibabel and surfaced as a bare
   `ImageFileError` traceback out of the middle of the stack, with nothing naming the real problem.

2. `magnitude` was advertised as `[optional]` for any stage where it wasn't the sole image input —
   a heuristic, not a fact about the method. 16 submissions read `magnitude.nii.gz` unconditionally
   while their `--magnitude` flag was optional, so omitting it produced a failure inside the
   container (a missing file) rather than an argparse error. `test_optional_magnitude_is_really_optional`
   is the audit that found them, kept as a test so a new submission can't reintroduce it.
"""
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

from qsm_ci import runner
from qsm_ci.params import _check_nifti
from qsm_ci.stages import MAGNITUDE_REQUIRED_STAGES, STAGES, is_optional

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = sorted((ROOT / "algorithms").glob("*/algorithm.yml"))


def _load(path):
    return yaml.safe_load(path.read_text())


# --------------------------------------------------------------------------- NIfTI input validation

def test_sidecars_in_a_glob_are_rejected_by_name():
    """The exact shape of failure 1: five images + their five sidecars."""
    paths = [f"anat/sub-01_echo-{i}_part-phase_MEGRE{ext}"
             for i in (1, 2) for ext in (".nii.gz", ".json")]
    with pytest.raises(SystemExit) as e:
        _check_nifti("phase", paths)
    msg = str(e.value)
    assert "sub-01_echo-1_part-phase_MEGRE.json" in msg      # names what was wrong
    assert "sub-01_echo-1_part-phase_MEGRE.nii.gz" not in msg  # and not what was fine
    assert ".nii*" in msg                                     # offers the narrower glob
    assert "automatically" in msg                             # and says not to bother passing them


def test_a_long_bad_list_is_truncated():
    with pytest.raises(SystemExit) as e:
        _check_nifti("magnitude", [f"e{i}.json" for i in range(9)])
    assert "... and 4 more" in str(e.value)


def test_non_sidecar_junk_gets_the_plain_message():
    with pytest.raises(SystemExit) as e:
        _check_nifti("mask", ["mask.txt"])
    msg = str(e.value)
    assert "mask.txt" in msg and "NIfTI" in msg
    assert "BIDS" not in msg        # the sidecar hint would be a red herring here


@pytest.mark.parametrize("paths", [["a.nii"], ["a.nii.gz"], ["a.nii", "b.nii.gz"], []])
def test_nifti_lists_pass(paths):
    _check_nifti("phase", paths)


def test_the_run_loop_validates_before_touching_nibabel(tmp_path, monkeypatch):
    """End to end through `qsm-ci run`: a sidecar in --phase exits cleanly, and never reaches the
    stacking code that used to raise ImageFileError."""
    sidecar = tmp_path / "sub-01_echo-1_part-phase_MEGRE.json"
    sidecar.write_text('{"EchoTime": 0.005, "MagneticFieldStrength": 3.0}')
    # ROMEO requires both of these; they exist but are never read — validation must fail first.
    mask = tmp_path / "mask.nii.gz"
    mask.write_bytes(b"")
    mag = tmp_path / "magnitude.nii.gz"
    mag.write_bytes(b"")

    def _boom(*a, **k):
        raise AssertionError("_place_echoes must not be reached")

    monkeypatch.setattr(runner, "_place_echoes", _boom)
    with pytest.raises(SystemExit) as e:
        runner.run_command(["romeo-qsmrs", "--phase", str(sidecar), "--magnitude", str(mag),
                            "--mask", str(mask), "--runner", "local"])
    assert "NIfTI" in str(e.value)


# --------------------------------------------------------------------------- the magnitude contract

def test_stage_level_magnitude_rules():
    """A stage whose every method needs the signal decay: magnitude is required, full stop."""
    for stage in MAGNITUDE_REQUIRED_STAGES:
        assert not is_optional(stage, "magnitude"), stage
    # and the legacy default still holds where the method says nothing
    assert is_optional("field-mapping", "magnitude")


def test_declaring_an_input_makes_it_required():
    algo = {"stage": "field-mapping", "inputs": ["phase", "magnitude", "mask", "params"]}
    assert not runner._optional(algo, "magnitude")


def test_optional_inputs_is_the_opt_out():
    algo = {"stage": "field-mapping", "inputs": ["phase", "magnitude", "mask", "params"],
            "optional_inputs": ["magnitude"]}
    assert runner._optional(algo, "magnitude")


def test_an_input_declared_outside_the_contract_is_a_required_extra():
    """MEDI's magnitude: not part of the `dipole` contract, but its code cannot run without it."""
    algo = {"stage": "dipole", "inputs": ["localfield", "mask", "params", "magnitude"]}
    assert "magnitude" in runner._consumes(algo)
    assert not runner._optional(algo, "magnitude")


def test_an_opted_in_extra_stays_optional():
    algo = {"stage": "dipole", "optional_inputs": ["magnitude"]}
    assert "magnitude" in runner._consumes(algo)
    assert runner._optional(algo, "magnitude")


@pytest.mark.parametrize("slug,required", [("romeo-qsmrs", True), ("medi-qsmrs", True),
                                           ("tfi-qsmrs", False)])
def test_real_manifests_drive_the_parser(slug, required):
    algo = _load(ROOT / "algorithms" / slug / "algorithm.yml")
    algo.setdefault("name", slug)
    parser = runner._build_run_parser(slug, algo)
    mandatory = {a.dest for a in parser._actions if a.required}
    assert ("magnitude" in mandatory) is required


# --------------------------------------------------------------------------- the audit, as a test

def _reads_magnitude_unconditionally(algo_dir: Path) -> bool:
    """Does this submission's code read magnitude.nii.gz without checking it is there?

    A guard is either inline (`[ -f "$IN/magnitude.nii.gz" ]`) or via a path variable
    (`magPath = fullfile(inp, 'magnitude.nii.gz'); exist(magPath, 'file')`), so check both.
    """
    body = ""
    for f in sorted(algo_dir.rglob("*")):
        if f.is_file() and f.suffix not in (".yml", ".md"):
            try:
                body += f.read_text(errors="ignore")
            except OSError:
                pass
    if not re.search(r"magnitude\.nii", body):
        return False
    if re.search(r"(-f|-e|exists?|isfile)[^\n]{0,80}magnitude\.nii", body):
        return False
    for m in re.finditer(r"(\w+)\s*=\s*[^\n]*magnitude\.nii[^\n]*", body):
        if re.search(rf"(exists?|isfile|-f|-e)\s*\(?\s*{m.group(1)}\b", body):
            return False
    return True


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.parent.name)
def test_optional_magnitude_is_really_optional(path):
    """If the CLI lets you omit --magnitude, the method must cope with the file not being there.

    Fix one of two ways: declare `inputs:` (listing magnitude makes it required), or guard for the
    file in run.sh/recon.m and record that with `optional_inputs: [magnitude]`.
    """
    algo = _load(path)
    if not isinstance(algo, dict) or algo.get("stage") not in STAGES:
        pytest.skip("not a stage submission")
    consumes = runner._consumes(algo)
    if "magnitude" not in consumes or not runner._optional(algo, "magnitude", consumes):
        return  # required, or never offered — nothing to promise
    assert not _reads_magnitude_unconditionally(path.parent), (
        f"{path.parent.name}: --magnitude is optional but the code reads magnitude.nii.gz "
        f"unconditionally; add it to `inputs:` or guard for it")


# ------------------------------------------------- the scorer must agree with the CLI, exactly

def test_the_scorer_passes_exactly_the_flags_the_cli_accepts():
    """`scripts/pipeline.py` decides which `--<artifact>` flags the scored run is given, and the CLI
    decides which it accepts. These were two hand-copied implementations of one rule, and they drifted
    the moment `inputs:` semantics changed on one side: an `inputs:` list naming an artifact outside
    the stage contract (MEDI's magnitude) was dropped by the scorer, so `--magnitude` went unpassed to
    a CLI that had just started requiring it, and both MEDI submissions DNF'd in CI.

    pipeline.py now calls runner._consumes. This pins that it keeps doing so, for every submission.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import pipeline
    finally:
        sys.path.pop(0)

    discovered = {a["slug"]: a["consumes"] for a in pipeline.discover_algorithms("sim")}
    assert discovered, "discovery found no submissions"
    for slug, consumes in discovered.items():
        algo = _load(ROOT / "algorithms" / slug / "algorithm.yml")
        assert consumes == runner._consumes(algo), (
            f"{slug}: the scorer would pass {consumes}, the CLI expects "
            f"{runner._consumes(algo)}")


@pytest.mark.parametrize("slug", ["medi-qsmrs", "medi-cornell"])
def test_medi_gets_its_magnitude_flag(slug):
    """The specific regression: a required input from outside the stage contract."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import pipeline
    finally:
        sys.path.pop(0)
    algo = next(a for a in pipeline.discover_algorithms("sim") if a["slug"] == slug)
    assert "magnitude" in algo["consumes"]
