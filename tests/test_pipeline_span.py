"""The `pipeline` span (a whole toolbox pipeline, raw echoes to χ; QSMxT/QSM-CI#421) and the
optional params.json fields it reads (`ImagingFrequency`, `Manufacturer`).

A pipeline makes its own mask, so it is given none; the χ-separation pipelines also write χ+/χ−,
the others do not, so those two are optional products: collected when written, not missing when
absent. The candidate submission's run.sh is checked with qsmxt stubbed: its BIDS conversion (the
4-D inputs split per echo, one sidecar per echo) and its mapping of qsmxt's files onto the contract.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

from qsm_ci import runner
from qsm_ci.containers import _param_env
from qsm_ci.params import _sidecar_to_params
from qsm_ci.stages import (OPTIONAL_PRODUCES, STAGES, is_optional, optional_products,
                           scorable)

ROOT = Path(__file__).resolve().parent.parent
_YML = yaml.safe_load((ROOT / "stages.yml").read_text())
CANDIDATE = ROOT / "algorithms" / "toolbox-pipeline-qsmrs"


# --- the registry ---------------------------------------------------------------------------------

def test_optional_produces_match_yaml():
    want = {n: s["optional_produces"] for n, s in {**_YML["stages"], **_YML["spans"]}.items()
            if "optional_produces" in s}
    assert OPTIONAL_PRODUCES == want, (
        "qsm_ci/stages.py OPTIONAL_PRODUCES drifted from stages.yml optional_produces — update it.")


def test_pipeline_span_contract():
    assert STAGES["pipeline"] == {"consumes": ["phase", "magnitude", "params"], "produces": ["chimap"]}
    assert optional_products("pipeline") == ["chi-para", "chi-dia"]
    assert optional_products("dipole") == []
    # the mask comes from the magnitude, so the magnitude cannot be left out
    assert not is_optional("pipeline", "magnitude")
    assert not is_optional("pipeline", "phase")
    # no brain mask among the inputs: qsm-ci run cannot score it
    assert not scorable("pipeline")


def _method(root: Path, script: str, slug: str = "pipe-method") -> Path:
    d = root / slug
    d.mkdir(parents=True)
    (d / "algorithm.yml").write_text(f"name: Pipe\nslug: {slug}\nstage: pipeline\nimage: bash:latest\n"
                                     "run: bash run.sh\nparameters:\n- name: pipeline\n"
                                     "  default: qsmxt-defaults\n  description: the pipeline\n")
    (d / "run.sh").write_text('set -euo pipefail\nIN="$1"; OUT="$2"\n' + script)
    return d


def _save(path: Path, data, affine=None) -> Path:
    nib.save(nib.Nifti1Image(np.asarray(data, np.float32), np.eye(4) if affine is None else affine),
             str(path))
    return path


def _inputs(tmp: Path, extra_params: "dict | None" = None, shape=(6, 5, 4), n_echoes=3):
    rng = np.random.default_rng(0)
    _save(tmp / "phase.nii.gz", rng.uniform(-np.pi, np.pi, shape + (n_echoes,)))
    _save(tmp / "magnitude.nii.gz", rng.uniform(1, 2, shape + (n_echoes,)))
    params = {"TE": [0.004 * (i + 1) for i in range(n_echoes)], "B0": 3.0, "B0_dir": [0, 0, 1],
              "voxel_size": [1, 1, 1], **(extra_params or {})}
    (tmp / "params.json").write_text(json.dumps(params))
    return ["--phase", str(tmp / "phase.nii.gz"), "--magnitude", str(tmp / "magnitude.nii.gz"),
            "--params", str(tmp / "params.json"), "--runner", "local"]


def test_run_mounts_the_three_inputs_and_no_mask(tmp_path):
    m = _method(tmp_path, '[ "$(cd "$IN" && ls | sort | tr "\\n" " ")" = '
                          '"magnitude.nii.gz params.json phase.nii.gz " ] || exit 3\n'
                          'cp "$IN/phase.nii.gz" "$OUT/chimap.nii.gz"\n')
    rc = runner.run_command([str(m), *_inputs(tmp_path), "-o", str(tmp_path / "out")],
                            log=lambda *_: None)
    assert rc == 0
    assert (tmp_path / "out" / "chimap.nii.gz").exists()


def test_run_refuses_a_mask_flag(tmp_path):
    m = _method(tmp_path, 'cp "$IN/phase.nii.gz" "$OUT/chimap.nii.gz"\n')
    _save(tmp_path / "mask.nii.gz", np.ones((6, 5, 4)))
    with pytest.raises(SystemExit):
        runner.run_command([str(m), *_inputs(tmp_path), "--mask", str(tmp_path / "mask.nii.gz")],
                           log=lambda *_: None)


def test_optional_products_are_collected_when_written(tmp_path):
    m = _method(tmp_path, 'for a in chimap chi-para chi-dia; do cp "$IN/phase.nii.gz" "$OUT/$a.nii.gz"; done\n')
    out = tmp_path / "out"
    assert runner.run_command([str(m), *_inputs(tmp_path), "-o", str(out)], log=lambda *_: None) == 0
    assert {p.name for p in out.iterdir()} == {"chimap.nii.gz", "chi-para.nii.gz", "chi-dia.nii.gz"}


def test_optional_products_absent_is_not_a_failure(tmp_path):
    m = _method(tmp_path, 'cp "$IN/phase.nii.gz" "$OUT/chimap.nii.gz"\n')
    out = tmp_path / "out"
    assert runner.run_command([str(m), *_inputs(tmp_path), "-o", str(out)], log=lambda *_: None) == 0
    assert {p.name for p in out.iterdir()} == {"chimap.nii.gz"}


def test_the_required_product_is_still_required(tmp_path):
    m = _method(tmp_path, 'cp "$IN/phase.nii.gz" "$OUT/chi-para.nii.gz"\n')
    with pytest.raises(SystemExit, match="chimap"):
        runner.run_command([str(m), *_inputs(tmp_path), "-o", str(tmp_path / "out")],
                           log=lambda *_: None)


def test_scorer_argv_gives_a_pipeline_an_output_directory(pipeline, tmp_path, monkeypatch):
    from scoring import cli_run_argv
    from qsm_ci.stages import ARTIFACT_FILE
    _method(tmp_path / "algos", 'true\n')
    monkeypatch.setenv("QSMCI_ALGORITHMS_DIR", str(tmp_path / "algos"))
    algo = next(a for a in pipeline.discover_algorithms() if a["slug"] == "pipe-method")
    assert algo["consumes"] == ["phase", "magnitude", "params"]
    assert algo["optional_produces"] == ["chi-para", "chi-dia"]
    argv = cli_run_argv(algo, tmp_path / "in", tmp_path / "out", ARTIFACT_FILE, "local")
    assert argv[argv.index("-o") + 1] == str(tmp_path / "out")
    assert "--mask" not in argv


def test_candidate_is_a_parity_only_pipeline_submission():
    meta = yaml.safe_load((CANDIDATE / "algorithm.yml").read_text())
    assert meta["stage"] == "pipeline" and meta["source"] == "qsmrs"
    # never scored or listed: the pinned qsmxt has no --pipeline, and it is a parity candidate
    assert meta.get("ci_skip") is True and meta.get("parity_only") is True
    assert [p["name"] for p in meta["parameters"]] == ["pipeline"]


# --- params.json: ImagingFrequency, Manufacturer -------------------------------------------------

def test_env_carries_imaging_frequency_and_manufacturer(tmp_path):
    (tmp_path / "params.json").write_text(json.dumps(
        {"TE": [0.004], "B0": 3.0, "ImagingFrequency": 123.243444, "Manufacturer": "Siemens"}))
    env = _param_env(tmp_path)
    assert env["QSMCI_IMAGING_FREQUENCY"] == "123.243444"
    assert env["QSMCI_MANUFACTURER"] == "Siemens"


def test_env_leaves_them_out_when_absent(tmp_path):
    (tmp_path / "params.json").write_text(json.dumps({"TE": [0.004], "B0": 3.0}))
    env = _param_env(tmp_path)
    assert "QSMCI_IMAGING_FREQUENCY" not in env and "QSMCI_MANUFACTURER" not in env


class _Args:
    te = None
    field_strength = None
    b0_dir = None
    voxel_size = [1.0, 1.0, 1.0]


def test_a_bids_sidecar_carries_them_into_params(tmp_path):
    side = {"EchoTime": 0.004, "MagneticFieldStrength": 3, "ImagingFrequency": 123.2,
            "Manufacturer": "Philips"}
    p = tmp_path / "sub-1_echo-1_part-phase_MEGRE.json"
    p.write_text(json.dumps(side))
    params = _sidecar_to_params(p, side, _Args(), "pipeline")
    assert params["ImagingFrequency"] == 123.2 and params["Manufacturer"] == "Philips"
    params = _sidecar_to_params(p, {"EchoTime": 0.004, "MagneticFieldStrength": 3}, _Args(),
                                "pipeline")
    assert "ImagingFrequency" not in params and "Manufacturer" not in params


def test_pack_dataset_carries_them_only_from_the_sidecars(tmp_path):
    import pack_dataset
    side = {"EchoTime": 0.004, "MagneticFieldStrength": 3.0, "B0_dir": [0, 0, 1]}
    (tmp_path / "sub-1_echo-1_part-phase_MEGRE.json").write_text(json.dumps(side))
    params = pack_dataset.params_from_sidecars(tmp_path)
    assert "ImagingFrequency" not in params and "Manufacturer" not in params  # nothing made up
    side.update(ImagingFrequency=127.76, Manufacturer="Philips")
    (tmp_path / "sub-1_echo-1_part-phase_MEGRE.json").write_text(json.dumps(side))
    params = pack_dataset.params_from_sidecars(tmp_path)
    assert params["ImagingFrequency"] == 127.76 and params["Manufacturer"] == "Philips"


# --- the candidate's run.sh, qsmxt stubbed ---------------------------------------------------------

# A stand-in for `qsmxt run BIDS OUT --pipeline ID ...`: it records its arguments and the dataset it
# was given, and writes a derivatives tree shaped like qsmxt's (published maps under sub-1/anat,
# steps under workflow/), each map a copy of echo 1's phase so the grid is the input's.
_STUB = r'''#!/usr/bin/env bash
set -euo pipefail
[ "$1" = run ] || exit 2
BIDS="$2"; OUT="$3"; shift 3
echo "$*" > "$STUB_LOG/args"
cp -r "$BIDS" "$STUB_LOG/bids"
SRC="$BIDS/sub-1/anat/sub-1_echo-1_part-phase_MEGRE.nii.gz"
D="$OUT/derivatives/qsmxt"
mkdir -p "$D/sub-1/anat" "$D/workflow/sub-1/unwrap" "$D/workflow/sub-1/bgremove"
gzip -dc "$SRC" > "$D/sub-1/anat/sub-1_Chimap.nii"
cp "$D/sub-1/anat/sub-1_Chimap.nii" "$D/sub-1/anat/sub-1_mask.nii"
cp "$D/sub-1/anat/sub-1_Chimap.nii" "$D/workflow/sub-1/unwrap/sub-1_desc-totalppm_fieldmap.nii"
cp "$D/sub-1/anat/sub-1_Chimap.nii" "$D/workflow/sub-1/bgremove/sub-1_localfield.nii"
if [ "${STUB_CHISEP:-}" = 1 ]; then
  for d in paramagnetic diamagnetic; do
    cp "$D/sub-1/anat/sub-1_Chimap.nii" "$D/sub-1/anat/sub-1_desc-${d}_Chimap.nii"
  done
fi
if [ -n "${STUB_OFFGRID:-}" ]; then
  cp "$STUB_OFFGRID" "$D/workflow/sub-1/bgremove/sub-1_localfield.nii"
fi
'''


@pytest.fixture
def stub_qsmxt(tmp_path):
    if not shutil.which("jq"):
        pytest.skip("run.sh needs jq")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    q = bin_dir / "qsmxt"
    q.write_text(_STUB)
    q.chmod(q.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "stub"
    log.mkdir()
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log)}, log


def _run_candidate(tmp_path, env_extra, params=None, config=None, gz=True, shape=(6, 5, 4)):
    inp, out, inter = tmp_path / "in", tmp_path / "out", tmp_path / "out" / "intermediates"
    inp.mkdir()
    inter.mkdir(parents=True)
    rng = np.random.default_rng(1)
    phase = rng.uniform(-np.pi, np.pi, shape + (3,)).astype(np.float32)
    mag = rng.uniform(1, 2, shape + (3,)).astype(np.float32)
    aff = np.array([[0.9, 0, 0, -3], [0, 1.1, 0, 2], [0, 0, 1.2, 5], [0, 0, 0, 1]])
    _save(inp / "phase.nii.gz", phase, aff)
    _save(inp / "magnitude.nii.gz", mag, aff)
    (inp / "params.json").write_text(json.dumps(
        {"TE": [0.004, 0.008, 0.012], "B0": 3.0, "B0_dir": [0.1, 0.0, 0.995],
         "voxel_size": [0.9, 1.1, 1.2], **(params or {})}))
    if config:
        (inp / "config.json").write_text(json.dumps(config))
    env = {**os.environ, **env_extra, "QSMCI_INTERMEDIATES": str(inter)}
    r = subprocess.run(["bash", str(CANDIDATE / "run.sh"), str(inp), str(out)], env=env,
                       capture_output=True, text=True)
    return r, phase, mag, aff, out, inter


def test_candidate_converts_to_bids_and_maps_the_outputs(tmp_path, stub_qsmxt):
    env, log = stub_qsmxt
    r, phase, mag, aff, out, inter = _run_candidate(
        tmp_path, env, params={"ImagingFrequency": 123.243444, "Manufacturer": "Siemens",
                               "B0_nominal": 2.89}, config={"pipeline": "medi-toolbox"})
    assert r.returncode == 0, r.stderr
    args = (log / "args").read_text().split()
    assert args[args.index("--pipeline") + 1] == "medi-toolbox"
    assert args[args.index("--output-space") + 1] == "acquired"

    anat = log / "bids" / "sub-1" / "anat"
    for e in range(3):
        for part, data in (("phase", phase), ("mag", mag)):
            img = nib.load(str(anat / f"sub-1_echo-{e + 1}_part-{part}_MEGRE.nii.gz"))
            assert img.shape == phase.shape[:3]
            assert np.array_equal(img.get_fdata(dtype=np.float32), data[..., e])   # bytes untouched
            assert np.allclose(img.affine, aff)
            side = json.loads((anat / f"sub-1_echo-{e + 1}_part-{part}_MEGRE.json").read_text())
            assert side == {"EchoTime": [0.004, 0.008, 0.012][e], "EchoNumber": e + 1,
                            "MagneticFieldStrength": 2.89, "B0_dir": [0.1, 0.0, 0.995],
                            "ImagingFrequency": 123.243444, "Manufacturer": "Siemens"}

    assert {p.name for p in out.glob("*.nii.gz")} == {"chimap.nii.gz"}   # no χ-separation here
    assert np.array_equal(nib.load(str(out / "chimap.nii.gz")).get_fdata(dtype=np.float32),
                          phase[..., 0])
    assert {p.name for p in inter.iterdir()} == {"mask.nii.gz", "totalfield.nii.gz",
                                                 "localfield.nii.gz"}


def test_candidate_sidecars_without_the_optional_fields(tmp_path, stub_qsmxt):
    env, log = stub_qsmxt
    r, *_ = _run_candidate(tmp_path, env)
    assert r.returncode == 0, r.stderr
    assert "--pipeline qsmxt-defaults" in (log / "args").read_text()
    side = json.loads((log / "bids" / "sub-1" / "anat" / "sub-1_echo-2_part-mag_MEGRE.json").read_text())
    assert side == {"EchoTime": 0.008, "EchoNumber": 2, "MagneticFieldStrength": 3.0,
                    "B0_dir": [0.1, 0.0, 0.995]}


def test_candidate_writes_the_chisep_maps_when_qsmxt_does(tmp_path, stub_qsmxt):
    env, _ = stub_qsmxt
    r, _, _, _, out, _ = _run_candidate(tmp_path, {**env, "STUB_CHISEP": "1"},
                                        config={"pipeline": "chi-sep-ilsqr"})
    assert r.returncode == 0, r.stderr
    assert {p.name for p in out.glob("*.nii.gz")} == {"chimap.nii.gz", "chi-para.nii.gz",
                                                      "chi-dia.nii.gz"}


def test_candidate_skips_an_intermediate_off_the_input_grid(tmp_path, stub_qsmxt):
    env, _ = stub_qsmxt
    off = tmp_path / "off.nii"
    _save(off, np.zeros((7, 5, 4)))   # qsmxt's working grid after a resampling to axial
    r, _, _, _, out, inter = _run_candidate(tmp_path, {**env, "STUB_OFFGRID": str(off)})
    assert r.returncode == 0, r.stderr
    assert not (inter / "localfield.nii.gz").exists()
    assert "localfield skipped" in r.stderr
    assert (inter / "totalfield.nii.gz").exists()


def test_candidate_refuses_echo_count_mismatch(tmp_path, stub_qsmxt):
    env, _ = stub_qsmxt
    r, *_ = _run_candidate(tmp_path, env, params={"TE": [0.004, 0.008]})
    assert r.returncode != 0 and "TE 2" in r.stderr
