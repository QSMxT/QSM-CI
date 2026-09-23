"""`qsm-ci new` starters — every scaffolded submission must RUN and honour the contract.

The generic starter used to assume "primary input in ppm + a mask input", which is wrong for the two
magnitude-primary stages: `brain-extraction` loaded `/input/mask.nii.gz`, its own *output*, and
placeholder-multiplied by it; `r2prime-generation` was labelled ppm for a map in Hz. The five stages
whose primary input is 4D (`phase` or `magnitude`) also multiplied a 4D volume by the 3D mask, so
their starters crashed on the first line of real work. This runs the Python starter for every stage
against contract-shaped fixtures and checks the artifact it writes.
"""
from __future__ import annotations

import json
import subprocess
import sys

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import templates
from qsm_ci.scaffold import STAGE_HELP
from qsm_ci.stages import ARTIFACT_FILE, ARTIFACT_UNIT, STAGES, produced_artifacts

SHAPE, NECHO = (8, 9, 10), 4
LANGS = ("python", "julia", "matlab", "rust")


def _fixtures(inp, consumes):
    """One contract-shaped file per consumed artifact: phase/magnitude 4D x,y,z,echo; the rest 3D."""
    aff, rng = np.diag([1.0, 1.0, 1.0, 1.0]), np.random.default_rng(0)
    for art in consumes:
        f = inp / ARTIFACT_FILE[art]
        if art == "params":
            f.write_text(json.dumps({"B0": 7.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1],
                                     "TE": [0.004, 0.012, 0.020, 0.028]}))
        elif art in ("phase", "magnitude"):
            nib.save(nib.Nifti1Image(rng.random(SHAPE + (NECHO,)).astype(np.float32), aff), f)
        elif art == "mask":
            nib.save(nib.Nifti1Image(np.ones(SHAPE, np.uint8), aff), f)
        else:
            nib.save(nib.Nifti1Image(rng.random(SHAPE).astype(np.float32), aff), f)


@pytest.mark.parametrize("stage", list(STAGES))
def test_python_starter_runs_and_writes_its_artifacts(stage, tmp_path):
    inp, out = tmp_path / "in", tmp_path / "out"
    inp.mkdir(), out.mkdir()
    _fixtures(inp, STAGES[stage]["consumes"])
    src = tmp_path / "recon.py"
    src.write_text(templates._recon_source(stage, "python", "T"))

    r = subprocess.run([sys.executable, str(src), str(inp), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, f"{stage} starter crashed:\n{r.stderr}"
    for art in produced_artifacts(stage):
        f = out / ARTIFACT_FILE[art]
        assert f.exists(), f"{stage} wrote no {art}"
        # Every produced artifact is 3D on the mask grid (CONTRACT.md, Artifacts).
        assert nib.load(f).shape == SHAPE, f"{stage}/{art} is not on the input grid"


@pytest.mark.parametrize("stage", list(STAGES))
def test_a_starter_never_reads_the_artifact_it_produces(stage):
    """brain-extraction used to load /input/mask.nii.gz — the mask it is supposed to create."""
    for art in produced_artifacts(stage):
        if art in STAGES[stage]["consumes"]:
            continue  # legitimately both (no stage does this today, but the contract allows it)
        for lang in LANGS:
            body = templates._recon_source(stage, lang, "T")
            reads = [ln for ln in body.splitlines()
                     if f"inp, \"{ARTIFACT_FILE[art]}\"" in ln or f"inp}}/{ARTIFACT_FILE[art]}" in ln
                     or f"inp, '{ARTIFACT_FILE[art]}'" in ln]
            assert not reads, f"{stage}/{lang} reads its own output: {reads}"


@pytest.mark.parametrize("stage", list(STAGES))
@pytest.mark.parametrize("lang", LANGS)
def test_every_token_is_substituted(stage, lang):
    body = templates._recon_source(stage, lang, "T")
    left = [ln for ln in body.splitlines()
            if "__" in ln.replace("__name__", "").replace("__main__", "")]
    assert not left, f"{stage}/{lang} has unsubstituted tokens: {left}"


@pytest.mark.parametrize("stage", list(STAGES))
def test_the_starter_states_the_right_output_unit(stage):
    """ppm for fields and χ, Hz for R2′, binary for a mask — not ppm for everything."""
    unit = ARTIFACT_UNIT[produced_artifacts(stage)[0]]
    assert f"({unit})" in templates._recon_source(stage, "python", "T")


def test_every_stage_has_interactive_help():
    """`qsm-ci new`'s stage menu printed a blank line for brain-extraction."""
    assert [s for s in STAGES if not STAGE_HELP.get(s)] == []


def test_artifact_unit_covers_every_volume_artifact():
    """`params` is a JSON document, not a volume; everything else has a unit the starters quote."""
    assert set(ARTIFACT_UNIT) == set(ARTIFACT_FILE) - {"params"}
