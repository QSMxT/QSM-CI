"""A boolean `--set NAME=VALUE` must reach the method.

`qsm-ci run --set deconvolve=false` arrives in the container as `{"deconvolve": false}` in
config.json. A run.sh that reads it with `jq -r '.deconvolve // empty'` drops it: jq's `//`
treats `false` like a missing key, so the method silently ran at its default. That is how the
V-SHARP parity pair compared STI Suite's undeconvolved V-SHARP with a deconvolved QSM.rs one.

For every submission whose algorithm.yml gives a parameter a boolean default and whose run.sh
reads that parameter, run the run.sh with a stand-in `qsmxt` that records its arguments, once
with no config.json and once with the opposite value, and check the call changes.
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
ALGORITHMS = ROOT / "algorithms"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh scripts need jq")


def _boolean_params():
    for yml in sorted(ALGORITHMS.glob("*/algorithm.yml")):
        run_sh = yml.parent / "run.sh"
        if not run_sh.exists():
            continue
        doc = yaml.safe_load(yml.read_text()) or {}
        text = run_sh.read_text()
        if "qsmxt " not in text:
            continue
        for p in doc.get("parameters") or []:
            if isinstance(p, dict) and isinstance(p.get("default"), bool) and f".{p['name']}" in text:
                yield pytest.param(yml.parent, p["name"], p["default"], id=f"{yml.parent.name}:{p['name']}")


def _run(algo: Path, tmp_path: Path, config: dict | None) -> str:
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
    log = tmp_path / "qsmxt.args"
    fake = bin_ / "qsmxt"
    fake.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" > "{log}"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    # Only the recorded call matters: a run.sh that then publishes qsmxt's outputs (which the
    # stand-in doesn't write) fails after it, so the exit status is not checked.
    log.unlink(missing_ok=True)
    subprocess.run(["bash", str(algo / "run.sh"), str(inp), str(out)], check=False, env=env,
                   capture_output=True, text=True)
    return log.read_text().strip()


@pytest.mark.parametrize("algo,name,default", list(_boolean_params()))
def test_the_opposite_boolean_reaches_qsmxt(algo, name, default, tmp_path):
    # qsm-ci run writes `--set NAME=true|false` to config.json as a JSON boolean (runner._coerce).
    assert _run(algo, tmp_path, None) != _run(algo, tmp_path, {name: not default}), (
        f"{algo.name}/run.sh ignores --set {name}={str(not default).lower()}")
