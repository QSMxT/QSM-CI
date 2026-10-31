"""Both WaveSep entries default Dr to the published value scaled with field, 137·B0/2.9 Hz/ppm.

WaveSep ships no Dr (its driver reads one per dataset), so the entries supply χ-separation's
published 137 Hz/ppm at 3 T, scaled with B0 as the SNU toolbox does. A flat 137 at every field was
2.4x too small at 7 T. Wiring only: the solver and qsmxt are stand-ins.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ALGORITHMS = ROOT / "algorithms"


def _params(b0: float) -> dict:
    return {"B0": b0, "B0_dir": [0, 0, 1], "TE": [0.004, 0.008], "voxel_size": [1, 1, 1]}


@pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh needs jq")
@pytest.mark.parametrize("b0,config,want", [
    (3.0, None, 137 * 3.0 / 2.9),
    (7.0, None, 137 * 7.0 / 2.9),
    (7.0, {"Dr": 200}, 200.0),
])
def test_wavesep_qsmrs_passes_the_field_scaled_dr(b0, config, want, tmp_path):
    inp, out, bin_ = tmp_path / "in", tmp_path / "out", tmp_path / "bin"
    for d in (inp, out, bin_):
        d.mkdir()
    (inp / "params.json").write_text(json.dumps(_params(b0)))
    if config is not None:
        (inp / "config.json").write_text(json.dumps(config))
    log = tmp_path / "qsmxt.args"
    fake = bin_ / "qsmxt"
    # Records its arguments and writes the two outputs run.sh then gzips (-o is a prefix).
    fake.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$*" > "{log}"\n'
        'while [ $# -gt 0 ]; do [ "$1" = -o ] && P="$2"; shift; done\n'
        'touch "${P}_desc-paramagnetic_Chimap.nii" "${P}_desc-diamagnetic_Chimap.nii"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(["bash", str(ALGORITHMS / "wavesep-qsmrs" / "run.sh"), str(inp), str(out)],
                   check=True, env=env, capture_output=True, text=True)
    args = log.read_text().split()
    assert float(args[args.index("--dr-pos") + 1]) == pytest.approx(want, rel=1e-9)
    assert float(args[args.index("--dr-neg") + 1]) == pytest.approx(want, rel=1e-9)


def _load_wavesep_recon(monkeypatch):
    """Import algorithms/wavesep/recon.py with its third-party solver and PyWavelets stubbed out."""
    solver = types.ModuleType("wavesep.utils.solver_wavesep_qsm")
    solver.Solver = object
    for name, mod in {"wavesep": types.ModuleType("wavesep"),
                      "wavesep.utils": types.ModuleType("wavesep.utils"),
                      "wavesep.utils.solver_wavesep_qsm": solver,
                      "pywt": types.ModuleType("pywt")}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("wavesep_recon", ALGORITHMS / "wavesep" / "recon.py")
    recon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recon)
    return recon


@pytest.mark.parametrize("b0", [1.5, 3.0, 7.0])
def test_wavesep_default_dr_scales_with_field(b0, monkeypatch):
    pytest.importorskip("nibabel")
    monkeypatch.delenv("WAVESEP_DR", raising=False)
    recon = _load_wavesep_recon(monkeypatch)
    assert recon.dr_value(_params(b0), {}) == pytest.approx(137 * b0 / 2.9)
    assert recon.dr_value(_params(b0), {"Dr": 120}) == 120.0
