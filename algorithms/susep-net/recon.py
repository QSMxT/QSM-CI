#!/usr/bin/env python3
"""QSM-CI `chi-separation` stage — SUSEP-Net (Li/Gao/Sun et al. 2025), PyTorch inference (CPU).

Isolated eval: reads the local field (ppm), χ_total/QSM (ppm), R2' (Hz), mask and params, runs the
trained SUSEP-Net network, and writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−).

SUSEP-Net (repo internal name "SQ-Net", arXiv:2506.13293) is a dual-branch 3D U-net that takes three
guidance maps — QSM, R2', local field — and predicts (χ+, χ−). The forward signature is
model(QSM, R2', LFS); the three are concatenated as channels [QSM, R2', LFS] and each is z-scored by
the training statistics in norm/all_mean_std.mat (keys qsm/r2_prime/lfs, plus chi_pos/chi_neg for the
outputs). NO Dr scaling: QSM and local field are fed in ppm, R2' in Hz, exactly as the authors do in
their test_demo.py (verified by reproducing their released demo outputs, corr > 0.98). The decoder
ends in a ReLU so both outputs are non-negative magnitudes — χ− is therefore already a POSITIVE
magnitude, matching the stage contract.

The net is fully convolutional; the released demo runs it whole-volume. We do the same, padding the
volume up to a multiple of 8 (three 2× max-pools) and cropping back afterwards. Inference is forced
onto CPU (CUDA disabled) like modip / inr-qsm.

Model files (SUSEPNet.pth + norm .mat) are baked into the container at $SUSEPNET_MODELS; for a local
run they sit next to this script (gitignored). No MATLAB / GPU needed.
"""
import json
import os
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # force CPU (mirror modip / inr-qsm)

import numpy as np
import nibabel as nib
import scipy.io as sio
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from susepnet_model import SUSEPNet

IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"
WEIGHTS = "SUSEPNet.pth"
NORM = "all_mean_std.mat"


def _models_dir():
    """SUSEPNet.pth + norm .mat location: $SUSEPNET_MODELS (baked in the container), else next to
    this script (gitignored, local run)."""
    env = os.environ.get("SUSEPNET_MODELS")
    if env and os.path.exists(os.path.join(env, WEIGHTS)):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return here


MODELS = _models_dir()


def load(name):
    img = nib.load(os.path.join(IN, name))
    return np.asarray(img.get_fdata(), dtype=np.float32), img


def _stats():
    """Per-map (mean, std) z-score constants from the training set. The .mat holds a nested MATLAB
    struct all_mean_std.<key>.{mean,std}."""
    a = sio.loadmat(os.path.join(MODELS, NORM))["all_mean_std"]

    def flt(x):
        x = np.asarray(x)
        while x.dtype == object or x.ndim > 0:
            x = np.asarray(np.asarray(x).ravel()[0])
        return float(x)

    def ms(k):
        return flt(a[k][0, 0]["mean"]), flt(a[k][0, 0]["std"])

    return {k: ms(k) for k in ("qsm", "lfs", "r2_prime", "chi_pos", "chi_neg")}


def main():
    field, fimg = load("localfield.nii.gz")   # ppm
    qsm, _ = load("chimap.nii.gz")             # ppm (χ_total)
    r2p, _ = load("r2prime.nii.gz")            # Hz
    mask = (load("mask.nii.gz")[0] > 0.5)

    S = _stats()
    torch.set_num_threads(max(1, os.cpu_count() or 1))

    def z(x, key):
        m, s = S[key]
        return ((x - m) / s) * mask

    X, Y, Z = qsm.shape
    pad = [(0, (-d) % 8) for d in (X, Y, Z)]   # up to a multiple of 8 (three 2× pools)

    def tens(x):
        return torch.tensor(np.pad(x, pad), dtype=torch.float32)[None, None]

    qsm_t = tens(z(qsm, "qsm"))
    r2p_t = tens(z(r2p, "r2_prime"))
    fld_t = tens(z(field, "lfs"))

    model = SUSEPNet()
    sd = torch.load(os.path.join(MODELS, WEIGHTS), map_location="cpu")
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    sd = {(k[7:] if k.startswith("module.") else k): v for k, v in sd.items()}
    model.load_state_dict(sd, strict=True)
    model.eval()

    with torch.no_grad():
        chi_pos, chi_neg = model(qsm_t, r2p_t, fld_t)[:2]

    pm, ps = S["chi_pos"]
    nm, ns = S["chi_neg"]
    xpos = (chi_pos[0, 0].numpy() * ps + pm)[:X, :Y, :Z] * mask   # χ+
    xneg = (chi_neg[0, 0].numpy() * ns + nm)[:X, :Y, :Z] * mask   # χ− (positive magnitude)

    os.makedirs(OUT, exist_ok=True)
    nib.save(nib.Nifti1Image(xpos.astype(np.float32), fimg.affine, fimg.header),
             os.path.join(OUT, "chi-para.nii.gz"))
    nib.save(nib.Nifti1Image(xneg.astype(np.float32), fimg.affine, fimg.header),
             os.path.join(OUT, "chi-dia.nii.gz"))
    print("susep-net: wrote chi-para/chi-dia", xpos.shape, flush=True)


if __name__ == "__main__":
    main()
