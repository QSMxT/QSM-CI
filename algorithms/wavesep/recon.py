#!/usr/bin/env python3
"""QSM-CI `chi-separation` stage — WaveSep (Fang et al., MLCN 2023), CPU, no weights.

Isolated eval: reads the χ_total/QSM (ppm), R2' (Hz), mask and params, runs the WaveSep wavelet-based
source separation, and writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−).

WaveSep is a purely iterative optimiser (NumPy + PyWavelets, no network, no pretrained weights). It
solves for the paramagnetic (χ+, iron) and diamagnetic (χ−, myelin·calcium) sources under two voxel-wise
data-fidelity terms plus a wavelet-domain L1 (soft-thresholding) sparsity prior:
    χ+ + χ−  ≈ χ_total (QSM)            [net susceptibility]
    χ+ − χ−  ≈ R2' / Dr                 [static-dephasing R2', single relaxivity kernel]
with the sign convention χ+ ≥ 0, χ− ≤ 0 internally. It uses NO B0 direction for the QSM path (unlike the
STI path), so single-orientation data needs no reorientation. We store χ− as a POSITIVE magnitude
(−xn) to match the stage contract.

Dr is the relaxometric constant (Hz/ppm) that puts R2'/Dr in ppm alongside χ_total. WaveSep ships no
value: its driver reads Dr_pos/Dr_neg per dataset from a params.json (wavesep/utils/run_wavesep_qsm.py:18,
data/yml/template_qsm.yml), and its in-vivo data are the SNU χ-separation data of co-author H.-G. Shin
(example_qsm.yml: SUB006, χ-sep-COSMOS labels). The published value for that data is χ-separation's own,
137 Hz/ppm, measured at 3 T (Shin et al. 2021), which the SNU χ-separation toolbox scales linearly with field:
Dr = 137·B0/2.9 (B0 = CF/42.58e6; QSM.rs src/separation/chi_sep_ilsqr.rs `toolbox_default_dr`). That is
our default, from params.json "B0": 141.7 Hz/ppm at 3 T, 330.7 at 7 T. Override with --set Dr, $WAVESEP_DR
or a "Dr" key in params.json. WaveSep's QSM model assumes Dr_pos == Dr_neg.

Vendored WaveSep source (github.com/ZhenghanFang/WaveSep) sits under ./wavesep, used unmodified; used
with the author's permission for academic benchmarking. Algorithm hyperparameters (alpha=0.2, Lambda=0.02,
db4, level=max, 100 iters w/ early stop) are the repo defaults from wavesep/qsm_sep.py.
"""
import json
import os
import sys
import tempfile

# WaveSep's solver module imports matplotlib at load (for a plot helper we never call). Give it a
# writable config dir so it doesn't warn when run as a non-root user with no writable HOME (CI).
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mplconfig"))

import numpy as np
import nibabel as nib
import pywt

# Import the vendored WaveSep package: next to this script (local run), else $WAVESEP_SRC (baked in the
# container). The source is gitignored, so one of the two must be present — see BUILD.md.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("WAVESEP_SRC"):
    sys.path.append(os.environ["WAVESEP_SRC"])
from wavesep.utils.solver_wavesep_qsm import Solver

IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"
# Repo defaults (WaveSep's own, from wavesep/qsm_sep.py). Each is overridable per run via
# `qsm-ci run wavesep --set <name>=<value>` (arrives as /input/config.json — see read_cfg / dr_value).
DEFAULT_WAVELET = "db4"
DEFAULT_ALPHA, DEFAULT_LAMBDA, DEFAULT_MAXIT = 0.2, 0.02, 100
# χ-separation's relaxometric constant (Shin et al. 2021) and the field it was measured at, as the SNU
# toolbox scales it: Dr = 137·B0/2.9 (see the module docstring).
DR_SHIN_2021, DR_REF_B0 = 137.0, 2.9


def load(name):
    img = nib.load(os.path.join(IN, name))
    return np.asarray(img.get_fdata(), dtype=np.float64), img


def pad_spec(shape, wavelet):
    """Pad each dim to a multiple of 2**L (L = pywt's max periodization level) so waverecn round-trips
    to the same shape — odd dims otherwise grow on reconstruction and break the solver."""
    dec = pywt.Wavelet(wavelet).dec_len
    P = 16
    while True:
        padded = [int(np.ceil(d / P)) * P for d in shape]
        L = pywt.dwt_max_level(min(padded), dec)
        if all(d % (2 ** L) == 0 for d in padded):
            return [(0, p - d) for d, p in zip(shape, padded)]
        P *= 2


def read_cfg():
    """Parameter overrides (`qsm-ci run --set NAME=VALUE`) arrive as /input/config.json; absent when no
    override is given. Only keys declared in algorithm.yml `parameters:` are ever written here."""
    p = os.path.join(IN, "config.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def default_dr(b0):
    """The published Dr scaled to this dataset's field: 137·B0/2.9 Hz/ppm."""
    return DR_SHIN_2021 * float(b0) / DR_REF_B0


def dr_value(params, cfg):
    # precedence: --set Dr (config.json) > $WAVESEP_DR > params.json "Dr" > 137·B0/2.9
    if cfg.get("Dr") is not None:
        return float(cfg["Dr"])
    env = os.environ.get("WAVESEP_DR")
    if env:
        return float(env)
    if isinstance(params, dict) and params.get("Dr") is not None:
        return float(params["Dr"])
    if not isinstance(params, dict) or params.get("B0") is None:
        sys.exit("wavesep: params.json has no B0; the default Dr (137*B0/2.9) needs it, or pass --set Dr=...")
    return default_dr(params["B0"])


def main():
    qsm, qimg = load("chimap.nii.gz")          # χ_total, ppm
    r2p, _ = load("r2prime.nii.gz")            # Hz
    mask = (load("mask.nii.gz")[0] > 0.5).astype(np.float64)
    with open(os.path.join(IN, "params.json")) as f:
        params = json.load(f)
    cfg = read_cfg()
    Dr = dr_value(params, cfg)
    wavelet = str(cfg.get("wavelet", DEFAULT_WAVELET))
    alpha = float(cfg.get("alpha", DEFAULT_ALPHA))
    lam = float(cfg.get("lambda", DEFAULT_LAMBDA))
    maxit = int(cfg.get("max_iter", DEFAULT_MAXIT))

    qsm = qsm.squeeze() * mask
    X, Y, Z = qsm.shape
    pad = pad_spec((X, Y, Z), wavelet)
    pf = lambda a: np.pad(a, pad)
    mask_p = pf(mask)
    qsm_p = pf(qsm) * mask_p
    r2p_p = (pf(r2p) * mask_p)[:, :, :, None]  # 4D: single orientation

    solver = Solver(qsm_p, r2p_p, Dr, Dr, mask_p, gt=None)
    # upstream solve() prints self.metrics[-1]; with no ground truth that list is empty -> attach a
    # no-op evaluator so it stays populated (no skimage compute, no change to the optimisation).
    solver.evaluator = type("_NoOpEval", (), {"evaluate": lambda self, x3d: {}})()
    xp, xn = solver.solve(alpha, lam, wavelet, level=None, maxit=maxit)

    xpos = (xp[:X, :Y, :Z] * mask).astype(np.float32)         # χ+
    xneg = (-xn[:X, :Y, :Z] * mask).astype(np.float32)        # χ− (positive magnitude)

    os.makedirs(OUT, exist_ok=True)
    nib.save(nib.Nifti1Image(xpos, qimg.affine, qimg.header), os.path.join(OUT, "chi-para.nii.gz"))
    nib.save(nib.Nifti1Image(xneg, qimg.affine, qimg.header), os.path.join(OUT, "chi-dia.nii.gz"))
    print(f"wavesep: wrote chi-para/chi-dia {xpos.shape} "
          f"Dr={Dr:.4g} lambda={lam:g} alpha={alpha:g} wavelet={wavelet} max_iter={maxit}", flush=True)


if __name__ == "__main__":
    main()
