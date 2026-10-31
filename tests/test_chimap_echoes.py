"""`chimap-echoes`: the per-echo χ(TE), an optional χ-separation input, packed, mounted and passed.

DECOMPOSE takes a QSM per echo (Chen et al. 2021, Eq. 4). Both entries used to repeat the single
chimap at every echo, which has no echo dependence to fit. A dataset can now ship
inputs/chimap-echoes.nii.gz (x,y,z,echo, ppm). A method opts in with `optional_inputs:`, gets it
mounted when it is there, and falls back to chimap when it isn't. Wiring only: tiny files and a
fixture method, plus decompose-qsmrs's opt-in and its run.sh with a stand-in qsmxt.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
from qsm_ci import runner
from qsm_ci.stages import ARTIFACT_FILE, ARTIFACT_NDIM, ARTIFACT_UNIT, STAGES
from scoring import cli_run_argv, gt_sources

ROOT = Path(__file__).resolve().parent.parent
DECOMPOSE = ROOT / "algorithms" / "decompose-qsmrs"
TE = [0.004, 0.008, 0.012]


def test_the_artifact():
    assert ARTIFACT_FILE["chimap-echoes"] == "chimap-echoes.nii.gz"
    assert ARTIFACT_NDIM["chimap-echoes"] == 4 and ARTIFACT_UNIT["chimap-echoes"] == "ppm"
    # optional by construction: in no stage's contract, so a dataset need not ship it
    assert all("chimap-echoes" not in s["consumes"] for s in STAGES.values())


def _fixture_method(root: Path) -> None:
    """A χ-separation method that opts in to chimap-echoes, as DECOMPOSE does."""
    d = root / "echoes-method"
    d.mkdir(parents=True)
    (d / "algorithm.yml").write_text(
        "name: echoes method\nslug: echoes-method\nstage: chi-separation\n"
        "inputs: [chimap, magnitude, mask, params]\noptional_inputs: [chimap-echoes]\n"
        "image: example/none\nrun: bash run.sh\n")


def test_discovery_and_scorer_mount_it_only_when_present(pipeline, tmp_path, monkeypatch):
    _fixture_method(tmp_path / "algos")
    monkeypatch.setenv("QSMCI_ALGORITHMS_DIR", str(tmp_path / "algos"))
    algo = {a["slug"]: a for a in pipeline.discover_algorithms(track="chisep")}["echoes-method"]
    assert "chimap-echoes" in algo["consumes"] and algo["optional"] == ["chimap-echoes"]

    ds = tmp_path / "ds"
    (ds / "inputs").mkdir(parents=True)
    (ds / "groundtruth").mkdir()
    for f in ("chimap.nii.gz", "magnitude.nii.gz", "mask.nii.gz"):
        (ds / "inputs" / f).write_bytes(b"x")
    (ds / "inputs" / "params.json").write_text(json.dumps({"TE": TE, "B0": 3}))
    idir = tmp_path / "in"
    pipeline.prepare_input(algo["consumes"], gt_sources(ds), idir, algo["optional"])
    assert not (idir / "chimap-echoes.nii.gz").exists()
    assert "--chimap-echoes" not in cli_run_argv(algo, idir, tmp_path / "out", ARTIFACT_FILE)

    (ds / "inputs" / "chimap-echoes.nii.gz").write_bytes(b"echoes")
    assert gt_sources(ds)["chimap-echoes"] == ds / "inputs" / "chimap-echoes.nii.gz"
    pipeline.prepare_input(algo["consumes"], gt_sources(ds), idir, algo["optional"])
    assert (idir / "chimap-echoes.nii.gz").read_bytes() == b"echoes"
    assert "--chimap-echoes" in cli_run_argv(algo, idir, tmp_path / "out", ARTIFACT_FILE)


def test_pack_dataset_ships_chimap_echoes(tmp_path):
    """qsm-forward's *_Chimap-echoes.nii lands as inputs/chimap-echoes.nii.gz, 4D, values intact."""
    bids = tmp_path / "bids"
    anat = bids / "sub-1" / "anat"
    der = bids / "derivatives" / "qsm-forward" / "sub-1" / "anat"
    anat.mkdir(parents=True)
    der.mkdir(parents=True)
    aff, shape = np.eye(4), (4, 4, 3)
    save = lambda p, a: nib.save(nib.Nifti1Image(np.asarray(a, np.float32), aff), str(p))
    for e, te in enumerate(TE, 1):
        for part in ("mag", "phase"):
            save(anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii", np.ones(shape))
        (anat / f"sub-1_echo-{e}_part-phase_MEGRE.json").write_text(
            json.dumps({"EchoTime": te, "MagneticFieldStrength": 3.0}))
    echoes = np.stack([np.full(shape, 0.01 * e) for e in range(1, len(TE) + 1)], axis=-1)
    for name, arr in {"Chimap": np.zeros(shape), "Chimap-pos": np.zeros(shape),
                      "Chimap-neg": np.zeros(shape), "mask": np.ones(shape),
                      "Chimap-echoes": echoes}.items():
        save(der / f"sub-1_{name}.nii", arr)
    out = tmp_path / "packed"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pack_dataset.py"), str(bids), str(out),
                    "--chisep"], check=True, capture_output=True, text=True)
    got = nib.load(str(out / "inputs" / "chimap-echoes.nii.gz")).get_fdata()
    assert got.shape == shape + (len(TE),)
    np.testing.assert_allclose(got, echoes, rtol=1e-6)


def test_gen_chisep_masks_every_echo_to_the_brain(tmp_path):
    import gen_chisep
    (tmp_path / "inputs").mkdir()
    aff, shape = np.eye(4), (4, 4, 3)
    mask = np.zeros(shape)
    mask[1:3, 1:3, :] = 1
    nib.save(nib.Nifti1Image(mask.astype(np.float32), aff), str(tmp_path / "inputs" / "mask.nii.gz"))
    nib.save(nib.Nifti1Image(np.ones(shape + (len(TE),), np.float32), aff),
             str(tmp_path / "inputs" / "chimap-echoes.nii.gz"))
    gen_chisep.mask_derived_to_brain(tmp_path)
    got = nib.load(str(tmp_path / "inputs" / "chimap-echoes.nii.gz")).get_fdata()
    assert got.shape == shape + (len(TE),)
    np.testing.assert_array_equal(got, np.repeat(mask[..., None], len(TE), axis=-1))


def test_decompose_qsmrs_opts_in_and_the_flag_is_optional():
    import yaml
    doc = yaml.safe_load((DECOMPOSE / "algorithm.yml").read_text())
    assert "chimap-echoes" in runner._consumes(doc) and runner._optional(doc, "chimap-echoes")
    flag = {a.dest: a for a in runner._build_run_parser("decompose-qsmrs", doc)._actions}["chimap_echoes"]
    assert not flag.required and flag.nargs == "+"   # one 4D file, or one 3D map per echo


def _run_decompose(tmp_path, *, per_echo_flag: bool, echoes: bool, b0: float = 3.0) -> list:
    inp, out, bin_ = tmp_path / "in", tmp_path / "out", tmp_path / "bin"
    for d in (inp, out, bin_):
        d.mkdir(exist_ok=True)
    (inp / "params.json").write_text(json.dumps({"TE": TE, "B0": b0, "B0_dir": [0, 0, 1]}))
    if echoes:
        (inp / "chimap-echoes.nii.gz").write_bytes(b"x")
    log = tmp_path / "qsmxt.args"
    help_text = "--qsm-per-echo --unwrap-phase" if per_echo_flag else "--qsm"
    (bin_ / "qsmxt").write_text(
        "#!/usr/bin/env bash\n"
        f'case " $* " in *" --help "*) echo "{help_text}"; exit 0;; esac\n'
        f'printf "%s\\n" "$*" > "{log}"\n'
        'while [ $# -gt 0 ]; do [ "$1" = -o ] && P="$2"; shift; done\n'
        'touch "${P}_desc-paramagnetic_Chimap.nii" "${P}_desc-diamagnetic_Chimap.nii"\n')
    (bin_ / "qsmxt").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(["bash", str(DECOMPOSE / "run.sh"), str(inp), str(out)], check=True, env=env,
                   capture_output=True, text=True)
    return log.read_text().split()


def _per_echo_args(args: list) -> list:
    if "--qsm-per-echo" not in args:
        return []
    rest = args[args.index("--qsm-per-echo") + 1:]
    return [a for a in rest[:next((i for i, a in enumerate(rest) if a.startswith("-")), len(rest))]]


@pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh needs jq")
def test_decompose_qsmrs_passes_chimap_echoes(tmp_path):
    got = _per_echo_args(_run_decompose(tmp_path, per_echo_flag=True, echoes=True))
    assert [Path(a).name for a in got] == ["chimap-echoes.nii.gz"]


@pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh needs jq")
def test_decompose_qsmrs_falls_back_to_chimap_per_echo(tmp_path):
    got = _per_echo_args(_run_decompose(tmp_path, per_echo_flag=True, echoes=False))
    assert [Path(a).name for a in got] == ["chimap.nii.gz"] * len(TE)


@pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh needs jq")
def test_decompose_qsmrs_on_a_qsmxt_without_the_flag(tmp_path):
    args = _run_decompose(tmp_path, per_echo_flag=False, echoes=True)
    assert "--qsm-per-echo" not in args and "--qsm" in args


@pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh needs jq")
def test_decompose_qsmrs_applies_qsmxts_7t_suggestions_only_at_7t(tmp_path):
    def pair(args, flag):
        return args[args.index(flag) + 1] if flag in args else None
    (tmp_path / "3t").mkdir(), (tmp_path / "7t").mkdir()
    at3 = _run_decompose(tmp_path / "3t", per_echo_flag=True, echoes=False, b0=2.89)
    at7 = _run_decompose(tmp_path / "7t", per_echo_flag=True, echoes=False, b0=6.98)
    assert pair(at3, "--unwrap-phase") is None and pair(at3, "--chi-bound") is None
    assert pair(at7, "--unwrap-phase") == "true" and pair(at7, "--chi-bound") == "echo-spacing"


def test_pack_dataset_ships_chimap_echoes(tmp_path):
    """qsm-forward's *_Chimap-echoes.nii lands as inputs/chimap-echoes.nii.gz, 4D, values intact."""
    bids = tmp_path / "bids"
    anat = bids / "sub-1" / "anat"
    der = bids / "derivatives" / "qsm-forward" / "sub-1" / "anat"
    anat.mkdir(parents=True)
    der.mkdir(parents=True)
    aff, shape = np.eye(4), (4, 4, 3)
    save = lambda p, a: nib.save(nib.Nifti1Image(np.asarray(a, np.float32), aff), str(p))
    for e, te in enumerate(TE, 1):
        for part in ("mag", "phase"):
            save(anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii", np.ones(shape))
        (anat / f"sub-1_echo-{e}_part-phase_MEGRE.json").write_text(
            json.dumps({"EchoTime": te, "MagneticFieldStrength": 3.0}))
    echoes = np.stack([np.full(shape, 0.01 * e) for e in range(1, len(TE) + 1)], axis=-1)
    for name, arr in {"Chimap": np.zeros(shape), "Chimap-pos": np.zeros(shape),
                      "Chimap-neg": np.zeros(shape), "mask": np.ones(shape),
                      "Chimap-echoes": echoes}.items():
        save(der / f"sub-1_{name}.nii", arr)
    out = tmp_path / "packed"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pack_dataset.py"), str(bids), str(out),
                    "--chisep"], check=True, capture_output=True, text=True)
    got = nib.load(str(out / "inputs" / "chimap-echoes.nii.gz")).get_fdata()
    assert got.shape == shape + (len(TE),)
    np.testing.assert_allclose(got, echoes, rtol=1e-6)


def test_gen_chisep_masks_every_echo_to_the_brain(tmp_path):
    import gen_chisep
    (tmp_path / "inputs").mkdir()
    aff, shape = np.eye(4), (4, 4, 3)
    mask = np.zeros(shape)
    mask[1:3, 1:3, :] = 1
    nib.save(nib.Nifti1Image(mask.astype(np.float32), aff), str(tmp_path / "inputs" / "mask.nii.gz"))
    nib.save(nib.Nifti1Image(np.ones(shape + (len(TE),), np.float32), aff),
             str(tmp_path / "inputs" / "chimap-echoes.nii.gz"))
    gen_chisep.mask_derived_to_brain(tmp_path)
    got = nib.load(str(tmp_path / "inputs" / "chimap-echoes.nii.gz")).get_fdata()
    assert got.shape == shape + (len(TE),)
    np.testing.assert_array_equal(got, np.repeat(mask[..., None], len(TE), axis=-1))
