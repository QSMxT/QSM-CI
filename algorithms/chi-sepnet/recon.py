#!/usr/bin/env python3
"""QSM-CI `chi-separation` stage — χ-sepnet (SNU-LIST, deep learning), ONNX inference.

Isolated eval: reads the local field (ppm), χ_total/QSM (ppm), R2' (Hz), mask and params, runs the
trained χ-sepnet network, and writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−).

The network (models/240904_xsepnet.onnx) takes a 3-channel 192x192x128 patch — [QSM, local field,
R2'/Dr] each z-scored by the training statistics in xsepnet_train_patch_norm_factor*.mat — and
predicts [χ+, χ−] (z-scored). We run it as an overlapping sliding window over the whole volume and
average the overlaps, then de-normalise. Dr = 114 Hz/ppm (the network's COSMOS-referenced relaxivity).

Units: the network was trained with the field and χ maps in ppm (not Hz) and R2' scaled to a
ppm-equivalent by dividing by Dr — so we feed localfield/chimap in ppm unchanged and r2prime/Dr.

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
DEFAULT_DR = 114.0    # the network's COSMOS-referenced relaxivity (Hz/ppm) — see read_dr()
PATCH = (192, 192, 128)
ONNX = "240904_xsepnet.onnx"
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
    """Dr (Hz/ppm) used to scale R2' into the network's input channel. Overridable via
    `qsm-ci run chi-sepnet --set Dr=...` (arrives as /input/config.json), else the trained default 114.
    NB: the net was trained at Dr=114 — moving it feeds off-distribution inputs, so this is a research
    knob, not an accuracy-tuning target."""
    p = os.path.join(IN, "config.json")
    if os.path.exists(p):
        with open(p) as f:
            v = json.load(f).get("Dr")
        if v is not None:
            return float(v)
    return DEFAULT_DR


def load(name):
    img = nib.load(os.path.join(IN, name))
    return np.asarray(img.get_fdata(), dtype=np.float64), img


def _starts(size, patch):
    if size <= patch:
        return [0]
    st = list(range(0, size - patch + 1, int(patch * 0.75)))
    if st[-1] != size - patch:
        st.append(size - patch)
    return st


def main():
    field, fimg = load("localfield.nii.gz")   # ppm
    qsm, _ = load("chimap.nii.gz")             # ppm (χ_total)
    r2p, _ = load("r2prime.nii.gz")            # Hz
    mask = (load("mask.nii.gz")[0] > 0.5)
    dr = read_dr()

    N = sio.loadmat(os.path.join(MODELS, NORM))
    def s(k):
        return float(N[k].ravel()[0])

    # 3 input channels in the order the network expects: [QSM, field, R2'/Dr], each z-scored.
    chans = [
        (qsm - s("cosmos_sus_mean")) / s("cosmos_sus_std"),
        (field - s("field_mean")) / s("field_std"),
        ((r2p / dr) - s("r2prime_mean")) / s("r2prime_std"),
    ]
    vol = np.stack([c * mask for c in chans]).astype(np.float32)   # (3, X, Y, Z)
    _, X, Y, Z = vol.shape
    pad = [max(0, PATCH[k] - (X, Y, Z)[k]) for k in range(3)]
    volp = np.pad(vol, ((0, 0), (0, pad[0]), (0, pad[1]), (0, pad[2])))
    _, Xp, Yp, Zp = volp.shape

    sess = ort.InferenceSession(os.path.join(MODELS, ONNX),
                                providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    acc = np.zeros((2, Xp, Yp, Zp), np.float64)
    wsum = np.zeros((Xp, Yp, Zp), np.float64)
    for x0 in _starts(Xp, PATCH[0]):
        for y0 in _starts(Yp, PATCH[1]):
            for z0 in _starts(Zp, PATCH[2]):
                sl = (slice(x0, x0 + PATCH[0]), slice(y0, y0 + PATCH[1]), slice(z0, z0 + PATCH[2]))
                patch = volp[:, sl[0], sl[1], sl[2]][None]
                out = sess.run(None, {iname: patch.astype(np.float32)})[0][0]
                acc[:, sl[0], sl[1], sl[2]] += out
                wsum[sl[0], sl[1], sl[2]] += 1.0
    acc /= np.maximum(wsum, 1.0)

    xpos = (acc[0] * s("x_pos_std") + s("x_pos_mean"))[:X, :Y, :Z] * mask   # χ+
    xneg = (acc[1] * s("x_neg_std") + s("x_neg_mean"))[:X, :Y, :Z] * mask   # χ− (positive magnitude)

    os.makedirs(OUT, exist_ok=True)
    nib.save(nib.Nifti1Image(xpos.astype(np.float32), fimg.affine, fimg.header),
             os.path.join(OUT, "chi-para.nii.gz"))
    nib.save(nib.Nifti1Image(xneg.astype(np.float32), fimg.affine, fimg.header),
             os.path.join(OUT, "chi-dia.nii.gz"))
    print("chi-sepnet: wrote chi-para/chi-dia", xpos.shape, "Dr=%g" % dr, flush=True)


if __name__ == "__main__":
    main()
