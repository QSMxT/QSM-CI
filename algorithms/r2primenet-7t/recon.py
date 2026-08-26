#!/usr/bin/env python3
"""QSM-CI `r2prime-generation` stage — R2PRIMEnet-7T (SNU-LIST, deep learning), ONNX inference.

R2PRIMEnet-7T (Jiye Kim, SNU-LIST; github.com/SNU-LIST/R2PRIMENET_7T, from "In-vivo high-resolution
χ-separation at 7T", arXiv:2410.12239) converts a 7T R2* map into a 3T-equivalent R2′ map — trained
specifically on 7T acquisitions, unlike the 3T R2PRIMEnet from the χ-sepnet pipeline. Reads the
multi-echo GRE magnitude, fits R2* (weighted log-linear least squares, an ARLO stand-in), runs the
network, and writes /output/r2prime.nii.gz (Hz).

Official test-time pipeline (Code/test.py + utils.test_dataset): R2* (Hz) clipped ≥0, scaled /114,
z-scored by the training statistics in r2pnet7T_norm_factor.mat, masked, zero-padded to multiples
of 64 (4 pooling levels), one whole-volume U-Net pass; output de-normalised and ×114 → Hz, negatives
clipped. Two deviations here, both documented:

  - Sliding-window 192×192×128 patches with overlap averaging instead of one whole-volume pass —
    the network is fully convolutional, and the whole padded scoring volume's activations don't fit
    a 16 GB CI runner. Patch dims are multiples of 64, matching the padding contract.
  - The network's output is R2′ in the 3T DOMAIN (its training reference; R2′ scales ~linearly with
    B0). The benchmark's truth and the downstream χ-separation methods expect native-field Hz, so
    the output is rescaled ×(B0/3) using params.json — a no-op at 3T.

Model + norm stats are baked into the container at $XSEPNET_MODELS; recon.py falls back to a local
copy (next to it) or the R2PRIMENET_7T checkout. onnxruntime does the inference — no torch needed.
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
DR = 114.0            # the network family's relaxivity scaling (Hz/ppm) — baked into training
PATCH = (192, 192, 128)   # multiples of 64 (4 pool levels)
ONNX = "r2pnet7T.onnx"
NORM = "r2pnet7T_norm_factor.mat"


def _models_dir():
    """ONNX model + norm .mat location: $XSEPNET_MODELS (baked in the container), else next to this
    script (gitignored, local run), else the SNU-LIST R2PRIMENET_7T checkout."""
    env = os.environ.get("XSEPNET_MODELS")
    if env and os.path.exists(os.path.join(env, ONNX)):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(here, ONNX)):
        return here
    return os.path.join(os.environ.get("R2PNET7T_DIR",
                        "/home/ashley/repos/qsm/R2PRIMENET_7T"), "CheckPoint")


MODELS = _models_dir()


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
    b0 = float(p.get("B0", 7.0))
    mag_img = nib.load(os.path.join(IN, "magnitude.nii.gz"))
    mag = np.nan_to_num(np.asarray(mag_img.get_fdata(), dtype=np.float64))
    mask = np.asarray(nib.load(os.path.join(IN, "mask.nii.gz")).get_fdata()) > 0.5
    if mag.ndim != 4 or mag.shape[-1] != len(tes):
        raise SystemExit(f"magnitude {mag.shape} inconsistent with {len(tes)} TEs")

    r2s = fit_r2star(mag, tes)                     # Hz (already clipped ≥0)

    N = sio.loadmat(os.path.join(MODELS, NORM))
    def s(k):
        return float(N[k].ravel()[0])

    # Official test-time normalisation: (R2*/114 − mean)/std, masked.
    vol = (((r2s / DR) - s("r2star_7T_mean")) / s("r2star_7T_std") * mask).astype(np.float32)
    X, Y, Z = vol.shape
    # pad each axis to a multiple of 64 AND at least the patch size (the sliding window needs it)
    tgt = [max(PATCH[k], 64 * int(np.ceil((X, Y, Z)[k] / 64))) for k in range(3)]
    pad = [tgt[k] - (X, Y, Z)[k] for k in range(3)]
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

    # De-normalise to 3T-domain Hz (×114, negatives clipped, official convention), then rescale to
    # the acquisition's native field (R2′ ∝ B0) so the output matches the benchmark's truth units.
    r2p_3t = np.clip((acc * s("r2prime_std") + s("r2prime_mean")) * DR, 0, None)[:X, :Y, :Z]
    r2p = (r2p_3t * (b0 / 3.0) * mask).astype(np.float32)

    os.makedirs(OUT, exist_ok=True)
    nib.save(nib.Nifti1Image(r2p, mag_img.affine, mag_img.header),
             os.path.join(OUT, "r2prime.nii.gz"))
    print("r2primenet-7t: R2* mean %.1f Hz -> R2' (3T-domain) mean %.1f Hz -> native (B0=%g) mean %.1f Hz"
          % (r2s[mask].mean(), r2p_3t[mask].mean(), b0, r2p[mask].mean()), flush=True)


if __name__ == "__main__":
    main()
