"""`qsm-ci run` works for EVERY stage in STAGES, not just the two the other tests drive.

The run parser, its help text and the params.json builder are generated from the stage contract, so
an assumption that holds for BFR/dipole (one primary path, a --mask input, a scorable output) used to
crash the neighbouring stages: field-mapping via --phase (a LIST was passed as a path), --truth on
brain-extraction (no --mask, no metric set), r2prime scored with the χ metric set, --phase optional for
field-mapping, and a valued option before the slug mis-parsed as the slug. One parametrised pass over
STAGES pins all of them at once.
"""
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import runner
from qsm_ci.params import _nifti_voxel_size, _params_dict, _sidecar_to_params
from qsm_ci.stages import ARTIFACT_FILE, ARTIFACT_KIND, STAGES, is_optional, scorable

SHAPE = (6, 6, 6)


def _algo(stage, **extra):
    return {"stage": stage, "name": f"test-{stage}", "slug": f"test-{stage}", **extra}


def _nii(path: Path, voxel=(0.7, 0.8, 0.9), value=None, seed=0, n_echo=None):
    rng = np.random.default_rng(seed)
    shape = SHAPE + ((n_echo,) if n_echo else ())
    data = np.full(shape, value, "float32") if value is not None else rng.normal(size=shape).astype("float32")
    aff = np.diag(list(voxel) + [1.0])
    nib.save(nib.Nifti1Image(data, aff), str(path))
    return str(path)


def _full_argv(tmp_path, stage, consumes, per_echo=False):
    """A complete, valid argument list for `stage`: every consumed image as a file (multi-echo ones
    as one 4D file or, with per_echo, three 3D echoes), acquisition flags where phase is consumed."""
    argv = [f"x-{stage}"]
    for art in consumes:
        if art == "params":
            continue
        if art in ("phase", "magnitude") and per_echo:
            files = [_nii(tmp_path / f"{art}_echo-{i}.nii.gz") for i in (1, 2, 3)]
            argv += [f"--{art}", *files]
        elif art in ("phase", "magnitude"):
            argv += [f"--{art}", _nii(tmp_path / ARTIFACT_FILE[art], n_echo=3)]
        elif art == "mask":
            argv += ["--mask", _nii(tmp_path / "mask.nii.gz", value=1.0)]
        else:
            argv += [f"--{art}", _nii(tmp_path / ARTIFACT_FILE[art])]
    if "phase" in consumes:
        argv += ["--te", "0.004", "0.012", "0.02", "--field-strength", "7"]
    return argv


@pytest.mark.parametrize("stage", sorted(STAGES))
def test_required_flags_follow_the_contract(stage):
    """phase is required wherever the stage consumes it; magnitude only when it's the sole image
    input; --truth/--seg exist only for scorable stages."""
    algo = _algo(stage)
    consumes = runner._consumes(algo)
    parser = runner._build_run_parser(algo["slug"], algo)
    required = {a.dest for a in parser._actions if a.required}
    for art in consumes:
        if art == "params":
            continue
        assert (art in required) == (not is_optional(stage, art, consumes)), (stage, art)
    if "phase" in STAGES[stage]["consumes"]:
        assert "phase" in required, f"{stage}: phase must be mandatory"
    opts = {o for a in parser._actions for o in a.option_strings}
    assert ("--truth" in opts) == scorable(stage)
    assert ("--seg" in opts) == scorable(stage)
    # the help text agrees with the parser about which inputs are optional
    help_text = runner._inputs_summary(algo["slug"], algo)
    for art in consumes:
        if art != "params":
            assert (f"--{art} PATH" in help_text)
            assert (("[optional]" in next(l for l in help_text.splitlines() if l.strip().startswith(f"--{art} ")))
                    == is_optional(stage, art, consumes))
    assert ("--truth" in help_text) == scorable(stage)


@pytest.mark.parametrize("stage", sorted(STAGES))
@pytest.mark.parametrize("per_echo", [False, True])
def test_full_argv_parses_and_builds_params_for_every_stage(tmp_path, stage, per_echo):
    """The documented flag path — files + acquisition flags, no --params — yields a params.json for
    every stage, reading the voxel size from the (possibly multi-file) primary input's header."""
    algo = _algo(stage)
    consumes = runner._consumes(algo)
    argv = _full_argv(tmp_path, stage, consumes, per_echo=per_echo)
    args = runner._build_run_parser(algo["slug"], algo).parse_args(argv)
    params = _params_dict(args, stage)
    assert params["voxel_size"] == pytest.approx([0.7, 0.8, 0.9])
    assert params["B0_dir"] == [0.0, 0.0, 1.0]
    if "phase" in consumes:
        assert params["TE"] == [0.004, 0.012, 0.02] and params["B0"] == 7.0
    else:
        assert params["TE"]  # never empty — a nominal placeholder for ppm stages


def test_sidecar_path_handles_multi_echo_lists_too(tmp_path):
    algo = _algo("field-mapping")
    consumes = runner._consumes(algo)
    argv = _full_argv(tmp_path, "field-mapping", consumes, per_echo=True)
    args = runner._build_run_parser(algo["slug"], algo).parse_args(argv)
    sidecar = tmp_path / "sub-1_echo-1_part-phase_MEGRE.json"
    sidecar.write_text('{"EchoTime": 0.004, "MagneticFieldStrength": 3}')
    params = _sidecar_to_params(sidecar, {"EchoTime": 0.004, "MagneticFieldStrength": 3}, args, "field-mapping")
    assert params["voxel_size"] == pytest.approx([0.7, 0.8, 0.9])


def test_unreadable_voxel_size_is_an_error_not_a_silent_default(tmp_path):
    algo = _algo("dipole")
    bad = tmp_path / "localfield.nii.gz"
    bad.write_bytes(b"not a nifti")
    argv = [algo["slug"], "--localfield", str(bad), "--mask", _nii(tmp_path / "mask.nii.gz", value=1.0)]
    args = runner._build_run_parser(algo["slug"], algo).parse_args(argv)
    with pytest.raises(SystemExit, match="voxel size"):
        _params_dict(args, "dipole")
    args = runner._build_run_parser(algo["slug"], algo).parse_args(argv + ["--voxel-size", "1", "1", "2"])
    assert _params_dict(args, "dipole")["voxel_size"] == [1.0, 1.0, 2.0]


def test_voxel_size_reads_nifti2_headers(tmp_path):
    img = nib.Nifti2Image(np.zeros(SHAPE, "float32"), np.diag([1.5, 1.5, 3.0, 1.0]))
    nib.save(img, str(tmp_path / "n2.nii.gz"))
    assert _nifti_voxel_size(tmp_path / "n2.nii.gz") == pytest.approx([1.5, 1.5, 3.0])


@pytest.mark.parametrize("artifact", sorted(ARTIFACT_KIND))
def test_score_uses_the_metric_set_of_the_artifact_kind(tmp_path, artifact):
    """r2prime (relaxation) gets the field set, not χ's; every kind reports coverage; the no-seg χ
    set matches what CI publishes (nrmse/hfen included, not just correlation+xsim)."""
    truth = _nii(tmp_path / "truth.nii.gz", seed=1)
    mask = _nii(tmp_path / "mask.nii.gz", value=1.0)
    metrics = runner._score(Path(truth), artifact, Path(truth), Path(mask), None)
    kind = ARTIFACT_KIND[artifact]
    assert metrics["coverage"] == 1.0
    if kind in ("field", "relaxation"):
        assert set(metrics) == {"nrmse", "nrmse_detrend", "correlation", "xsim", "coverage"}
    elif kind == "chi":
        assert {"nrmse", "nrmse_detrend", "hfen", "correlation", "xsim"} <= set(metrics)
        assert "nrmse_dgm" not in metrics  # region metrics need --seg
    else:
        assert "xsim" in metrics and "nrmse" in metrics


def test_opted_in_phase_is_optional_for_a_chisep_method():
    algo = _algo("chi-separation", optional_inputs=["phase"])
    consumes = runner._consumes(algo)
    assert "phase" in consumes
    parser = runner._build_run_parser(algo["slug"], algo)
    assert not next(a for a in parser._actions if a.dest == "phase").required


@pytest.mark.parametrize("argv,slug", [
    (["tkd", "--localfield", "lf.nii.gz"], "tkd"),
    (["--runner", "local", "./my-method", "--localfield", "lf.nii.gz"], "./my-method"),
    (["--runner=local", "tkd"], "tkd"),
    (["--te", "0.004", "0.012", "--field-strength", "7", "romeo", "--phase", "p.nii.gz"], "romeo"),
    # a slug straight after a greedy (nargs="+") option is swallowed as one of its values — by
    # argparse too ("invalid float value: 'romeo'"), so None is the honest answer here
    (["--te", "0.004", "0.012", "romeo", "--phase", "p.nii.gz"], None),
    (["--phase", "e1.nii.gz", "e2.nii.gz", "--b0-dir", "0", "0", "-1", "romeo"], "romeo"),
    (["--set", "lambda=0.1", "-o", "out/", "medi", "--localfield", "lf.nii.gz"], "medi"),
    (["--help"], None),
    ([], None),
])
def test_find_slug_skips_option_values(argv, slug):
    assert runner._find_slug(argv) == slug


def test_out_path_treats_a_trailing_slash_as_a_directory(tmp_path):
    assert runner._out_path("out/", "chimap", multi=False) == Path("out") / "chimap.nii.gz"
    assert runner._out_path("my.nii.gz", "chimap", multi=False) == Path("my.nii.gz")
    (tmp_path / "existing").mkdir()
    assert runner._out_path(str(tmp_path / "existing"), "chimap", multi=False) == tmp_path / "existing" / "chimap.nii.gz"
    assert runner._out_path("anything", "chi-dia", multi=True) == Path("anything") / "chi-dia.nii.gz"
