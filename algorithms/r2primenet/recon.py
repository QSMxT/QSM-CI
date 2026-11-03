#!/usr/bin/env python3
"""QSM-CI `r2prime-generation` stage — R2PRIMEnet (SNU-LIST, deep learning), ONNX inference.

R2PRIMEnet is the R2*→R2′ conversion network from the χ-sepnet pipeline (Kim et al., "χ-sepnet:
Deep neural network for magnetic susceptibility source separation", Hum Brain Mapp 2025,
doi:10.1002/hbm.70136): when no spin-echo acquisition provides a measured R2 (the GRE-only
condition), it synthesizes R2′ from the GRE-derived R2* map. Composing this generator with the
χ-sepnet submission reproduces the paper's χ-sepnet-R2* variant (the toolbox ships ONE final
χ-sepnet network — the R2* pipeline differs only in feeding it R2PRIMEnet's synthetic R2′).

Reads the multi-echo GRE magnitude, fits R2* with ARLO as the toolbox does, runs R2PRIMEnet, and
writes /output/r2prime.nii.gz (Hz).

R2* is the toolbox's own (χ-separation toolbox v1.1.3, `Chisep_script.m` l. 84-93):
`if use_arlo(TE), r2star = r2star_arlo(mag_multi_echo, TE*1000, mask_brain)`, else `r2star_nnls`.
Both are P-code; they were run as black boxes in licensed MATLAB R2023b on Bunya (2026-11-02,
QSMxT/QSM-CI#301):
  - `r2star_arlo` is MEDI's `arlo.m` (2024.11.26) on the echoes with TE in ms, zero outside the mask,
    negative rates kept: against `arlo(TE_s, mag)` inside the mask it differs by 0 on the in-vivo
    chi-separation case (184x256x128, 5 echoes) and by 2e-16 relative on chisep-mc. `fit_r2star`
    below is `arlo.m` line for line, in float64.
  - `use_arlo` is true for three or more evenly spaced echoes (spacing equal to about 1e-4 of the
    unit), when TE is a column vector. (With a row vector, as the script's own header writes TE, it
    is always false, so the script falls back to NNLS; the GUI path and the network's training used
    ARLO.) This entry follows ARLO's rule and refuses echo times ARLO would not take, rather than
    substitute a fit: the toolbox's `r2star_nnls` (a parfor nonlinear fit, non-negative) is not
    reproduced here.

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


def evenly_spaced(tes):
    """`use_arlo`'s rule (toolbox v1.1.3, probed as a black box): three or more echoes, evenly
    spaced. The probe put its tolerance between 1e-4 and 1e-3 of the spacing's unit (ms):
    [5 11 17 23 29.0001] passes, 29.001 does not."""
    t = np.asarray(tes, np.float64) * 1000.0           # ms, as the toolbox passes TE
    if t.size < 3:
        return False
    d = np.diff(t)
    return bool(np.all(np.abs(d - d[0]) <= 5e-4))


def fit_r2star(mag, tes, mask):
    """R2* (Hz) by ARLO: MEDI's arlo.m (2024.11.26) line for line, which is what the toolbox's
    r2star_arlo computes (mag: X,Y,Z,E; tes: E, seconds). Negative rates are kept, NaN and Inf are 0
    (arlo.m), and the map is 0 outside the mask (r2star_arlo)."""
    y = np.asarray(mag, np.float64)
    te = np.asarray(tes, np.float64)
    nte = te.size
    yy = np.zeros(y.shape[:-1]); yx = np.zeros(y.shape[:-1])
    beta_yx = np.zeros(y.shape[:-1]); beta_xx = np.zeros(y.shape[:-1])
    for j in range(nte - 2):
        alpha = (te[j + 2] - te[j]) * (te[j + 2] - te[j]) / 2 / (te[j + 1] - te[j])
        tmp = (2 * te[j + 2] * te[j + 2] - te[j] * te[j + 2] - te[j] * te[j]
               + 3 * te[j] * te[j + 1] - 3 * te[j + 1] * te[j + 2]) / 6
        beta = tmp / (te[j + 2] - te[j + 1])
        gamma = tmp / (te[j + 1] - te[j])
        y1 = (y[..., j] * (te[j + 2] - te[j] - alpha + gamma) + y[..., j + 1] * (alpha - beta - gamma)
              + y[..., j + 2] * beta)
        x1 = y[..., j] - y[..., j + 2]
        yy = yy + y1 * y1
        yx = yx + y1 * x1
        beta_yx = beta_yx + beta * y1 * x1
        beta_xx = beta_xx + beta * x1 * x1
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = (yx + beta_xx) / (beta_yx + yy)
    r2[~np.isfinite(r2)] = 0.0
    return r2 * mask


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
    if not evenly_spaced(tes):
        raise SystemExit(f"r2primenet: the toolbox fits R2* with ARLO only for 3+ evenly spaced "
                         f"echoes (use_arlo); TE = {list(tes)} s would take its NNLS fit, which this "
                         f"entry does not reproduce")

    r2s = fit_r2star(mag, tes, mask)               # Hz
    # float32 out, whatever the magnitude's own type (an int16 header would quantise the map).
    hdr = mag_img.header.copy()
    hdr.set_data_dtype(np.float32)
    inter = os.environ.get("QSMCI_INTERMEDIATES")
    if inter:                                      # CONTRACT.md "Intermediates"
        os.makedirs(inter, exist_ok=True)
        nib.save(nib.Nifti1Image(r2s.astype(np.float32), mag_img.affine, hdr),
                 os.path.join(inter, "r2star.nii.gz"))

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
    nib.save(nib.Nifti1Image(r2p.astype(np.float32), mag_img.affine, hdr),
             os.path.join(OUT, "r2prime.nii.gz"))
    print("r2primenet: R2* mean %.1f Hz -> R2' mean %.1f Hz, Dr=%g"
          % (r2s[mask].mean(), r2p[mask].mean(), dr), flush=True)


if __name__ == "__main__":
    main()
