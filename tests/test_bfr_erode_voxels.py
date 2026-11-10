"""`erode_voxels` on the background-removal wrappers erodes the mask before the method runs.

`qsm-ci run --set erode_voxels=N` must make run.sh erode the given mask by N voxels with
`qsmxt mask erode` (the erosion `qsmxt run --bf-erode-voxels` applies) and hand the eroded mask to
`qsmxt bgremove`, with the field unchanged. At 0, or with no config.json, nothing is eroded.
Wiring only: a stand-in `qsmxt` records every call.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = ["harperella-qsmrs", "iharperella-qsmrs", "pdf-qsmrs", "lbv-qsmrs"]

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh scripts need jq")


def _calls(algo: str, tmp_path: Path, config: dict | None) -> list[str]:
    inp, out, bin_ = tmp_path / "in", tmp_path / "out", tmp_path / "bin"
    for d in (inp, out, bin_):
        d.mkdir(exist_ok=True)
    (inp / "params.json").write_text(json.dumps({
        "B0": 3.0, "B0_dir": [0, 0, 1], "TE": [0.004, 0.008], "voxel_size": [1, 1, 1]}))
    cfg = inp / "config.json"
    if config is None:
        cfg.unlink(missing_ok=True)
    else:
        cfg.write_text(json.dumps(config))
    log = tmp_path / "qsmxt.calls"
    log.unlink(missing_ok=True)
    fake = bin_ / "qsmxt"
    # `--help` calls are how the wrappers probe the qsmxt version: answer as a current qsmxt.
    fake.write_text(f'#!/usr/bin/env bash\n'
                    f'case "$*" in *--help*) echo "--field-strength --depth --n-cg"; exit 0;; esac\n'
                    f'printf "%s\\n" "$*" >> "{log}"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(["bash", str(ROOT / "algorithms" / algo / "run.sh"), str(inp), str(out)],
                   check=False, env=env, capture_output=True, text=True)
    return log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("algo", WRAPPERS)
def test_erode_voxels_erodes_the_mask_bgremove_reads(algo, tmp_path):
    inp_mask = str(tmp_path / "in" / "mask.nii.gz")
    for config in (None, {"erode_voxels": 0}, {"tol": 1e-3}):
        calls = _calls(algo, tmp_path, config)
        assert not any(c.startswith("mask erode") for c in calls), (config, calls)
        assert any(c.startswith("bgremove") and f"-m {inp_mask}" in c for c in calls), (config, calls)

    calls = _calls(algo, tmp_path, {"erode_voxels": 2})
    erode = [c for c in calls if c.startswith("mask erode")]
    assert len(erode) == 1 and erode[0].startswith(f"mask erode {inp_mask} -o ") and erode[0].endswith("--iterations 2"), calls
    eroded = erode[0].split(" -o ")[1].split()[0]
    bg = [c for c in calls if c.startswith("bgremove")]
    assert len(bg) == 1 and f"-m {eroded}" in bg[0] and str(tmp_path / "in" / "totalfield.nii.gz") in bg[0], calls
    assert calls.index(erode[0]) < calls.index(bg[0])


@pytest.mark.parametrize("algo", WRAPPERS)
def test_erode_voxels_is_a_declared_parameter_defaulting_to_0(algo):
    doc = yaml.safe_load((ROOT / "algorithms" / algo / "algorithm.yml").read_text())
    p = [p for p in doc["parameters"] if p["name"] == "erode_voxels"]
    assert len(p) == 1 and p[0]["default"] == 0
