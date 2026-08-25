#!/usr/bin/env python3
"""QSM-CI `r2prime-generation` stage — R2PRIMEnet (SNU-LIST, deep learning), ONNX inference.

R2PRIMEnet is the R2*→R2′ conversion network from the χ-sepnet pipeline (Kim et al., "χ-sepnet:
Deep neural network for magnetic susceptibility source separation", Hum Brain Mapp 2025,
doi:10.1002/hbm.70136): when no spin-echo acquisition provides a measured R2 (the GRE-only
condition), it synthesizes R2′ from the GRE-derived R2* map. Composing this generator with the
χ-sepnet submission reproduces the paper's χ-sepnet-R2* variant (the toolbox ships ONE final
χ-sepnet network — the R2* pipeline differs only in feeding it R2PRIMEnet's synthetic R2′).

Reads the multi-echo GRE magnitude, fits R2* (weighted log-linear least squares, an ARLO stand-in),
runs R2PRIMEnet, and writes /output/r2prime.nii.gz (Hz).

The network (models/240531_R2PRIMEnet.onnx) takes a single-channel 192x192x128 patch — R2*/Dr
z-scored by the training statistics in xsepnet_train_patch_norm_factor*.mat — and predicts R2′/Dr
(z-scored). We run it as an overlapping sliding window over the whole volume and average the
overlaps, then de-normalise and clip negatives to zero (the paper's convention). Dr = 114 Hz/ppm
(the network family's COSMOS-referenced relaxivity; the official SNU training code scales every
relaxation map by Dr, custom_dataset.py).

Model files (ONNX + norm .mat) are baked into the container at $XSEPNET_MODELS; for a local run they
sit next to this script or in the SNU-LIST toolbox's models/ dir. onnxruntime does the inference, so
no MATLAB / Deep Learning Toolbox is needed.
"""
import json
import os
import sys

import numpy as np
import nibabel as nib
import scipy.io as sio
import onnxruntime as ort

IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"
DEFAULT_DR = 114.0    # the network family's COSMOS-referenced relaxivity (Hz/ppm) — see read_dr()
PATCH = (192, 192, 128)
ONNX = "240531_R2PRIMEnet.onnx"
NORM = "xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat"


def _models_dir():
    """ONNX model + norm .mat location: $XSEPNET_MODELS (baked in the container), else next to this
    script (gitignored, local run), else the SNU-LIST toolbox's models/ dir."""
    env = os.environ.get("XSEPNET_MODELS")
    if env and os.path.exists(os.path.join(env, ONNX)):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(here, ONNX)):
        return here
    tb = os.environ.get("CHISEP_TOOLBOX", "/home/ashley/repos/qsm/chi-separation/Chisep_Toolbox_v1.1.3")
    return os.path.join(tb, "models")


MODELS = _models_dir()


def read_dr():
    """Dr (Hz/ppm) used to scale R2* into the network's input channel (and R2′ back out).
    Overridable via `qsm-ci run r2primenet --set Dr=...` (arrives as /input/config.json), else the
    trained default 114. NB: the net was trained at Dr=114 — moving it feeds off-distribution
    inputs, so this is a research knob, not an accuracy-tuning target."""
    p = os.path.join(IN, "config.json")
    if os.path.exists(p):
        with open(p) as f:
            v = json.load(f).get("Dr")
        if v is not None:
            return float(v)
    return DEFAULT_DR


def fit_r2star(mag, tes):
    """R2* (Hz) by weighted log-linear least squares over echoes (mag: X,Y,Z,E; tes: E, seconds).
    Magnitude-weighted so noisy late echoes don't dominate; a robust stand-in for ARLO."""
    mag = np.clip(np.asarray(mag, np.float64), 1e-9, None)
    t = np.asarray(tes, np.float64)
    w = mag ** 2                                   # weight ∝ magnitude² (SNR)
    logm = np.log(mag)
    sw = w.sum(-1)
    tbar = (w * t).sum(-1) / sw
    lbar = (w * logm).sum(-1) / sw
    cov = (w * (t - tbar[..., None]) * (logm - lbar[..., None])).sum(-1)
    var = (w * (t - tbar[..., None]) ** 2).sum(-1)
    slope = np.divide(cov, var, out=np.zeros_like(cov), where=var > 0)
    return np.clip(-slope, 0, None)                # R2* = −slope of log-magnitude vs TE


def _starts(size, patch):
    if size <= patch:
        return [0]
    st = list(range(0, size - patch + 1, int(patch * 0.75)))
    if st[-1] != size - patch:
        st.append(size - patch)
    return st


def main():
    p = json.loads(open(os.path.join(IN, "params.json")).read())
    tes = np.asarray(p["TE"], np.float64)          # seconds
    mag_img = nib.load(os.path.join(IN, "magnitude.nii.gz"))
    mag = np.nan_to_num(np.asarray(mag_img.get_fdata(), dtype=np.float64))
    mask = np.asarray(nib.load(os.path.join(IN, "mask.nii.gz")).get_fdata()) > 0.5
    if mag.ndim != 4 or mag.shape[-1] != len(tes):
        raise SystemExit(f"magnitude {mag.shape} inconsistent with {len(tes)} TEs")
    dr = read_dr()

    r2s = fit_r2star(mag, tes)                     # Hz

    N = sio.loadmat(os.path.join(MODELS, NORM))
    def s(k):
        return float(N[k].ravel()[0])

    # Single input channel: R2*/Dr, z-scored by the training statistics, masked.
    vol = (((r2s / dr) - s("r2star_mean")) / s("r2star_std") * mask).astype(np.float32)
    X, Y, Z = vol.shape
    pad = [max(0, PATCH[k] - (X, Y, Z)[k]) for k in range(3)]
    volp = np.pad(vol, ((0, pad[0]), (0, pad[1]), (0, pad[2])))
    Xp, Yp, Zp = volp.shape

    sess = ort.InferenceSession(os.path.join(MODELS, ONNX),
                                providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    acc = np.zeros((Xp, Yp, Zp), np.float64)
    wsum = np.zeros((Xp, Yp, Zp), np.float64)
    for x0 in _starts(Xp, PATCH[0]):
        for y0 in _starts(Yp, PATCH[1]):
            for z0 in _starts(Zp, PATCH[2]):
                sl = (slice(x0, x0 + PATCH[0]), slice(y0, y0 + PATCH[1]), slice(z0, z0 + PATCH[2]))
                patch = volp[sl][None, None]
                out = sess.run(None, {iname: patch.astype(np.float32)})[0][0, 0]
                acc[sl] += out
                wsum[sl] += 1.0
    acc /= np.maximum(wsum, 1.0)

    # De-normalise (z-score -> R2'/Dr -> Hz); negatives clipped to zero per the paper's convention.
    r2p = np.clip((acc * s("r2prime_std") + s("r2prime_mean")) * dr, 0, None)[:X, :Y, :Z] * mask

    os.makedirs(OUT, exist_ok=True)
    nib.save(nib.Nifti1Image(r2p.astype(np.float32), mag_img.affine, mag_img.header),
             os.path.join(OUT, "r2prime.nii.gz"))
    print("r2primenet: R2* mean %.1f Hz -> R2' mean %.1f Hz, Dr=%g"
          % (r2s[mask].mean(), r2p[mask].mean(), dr), flush=True)


if __name__ == "__main__":
    main()
