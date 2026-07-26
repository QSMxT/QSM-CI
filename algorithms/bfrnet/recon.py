#!/usr/bin/env python3
"""QSM-CI `bfr` stage — BFRnet deep-learning background field removal (MATLAB-free, ONNX Runtime).

BFRnet is a 3D dual-frequency octave-convolution U-net that predicts the BACKGROUND field from the
total field; the local tissue field is total - background, masked. Everything is in ppm (the network
never sees TE/B0/B0_dir). This is a faithful port of the authors' MATLAB network: the trained
`BFRnet.mat` DAGNetwork was exported to ONNX with `exportONNXNetwork`, reproducing MATLAB `predict`
to max |Δ| = 9e-8.

Memory / tiling
---------------
Running the net on the whole challenge volume (164x205x205) peaks at ~18.7 GB — it gets OOM-killed
(exit 137) on the 16 GB hosted runner. The net is fully convolutional, so we do memory-bounded
sliding-window inference: predict the background on overlapping cubic patches and blend them with a
separable Hann window (the background field is smooth, so overlap-blending is seamless). Larger
patches see more context and track the whole-volume result more closely, so we use the largest patch
that fits the memory budget: 128^3 patches with 32-voxel overlap reproduce the full-volume background
to correlation 0.9991 (max |Δ| ~1e-1 ppm only at a few mask-edge voxels) at ~5.3 GB peak — safe under
the scorer's 2-way container concurrency. onnxruntime's CPU memory arena is disabled so peak stays at
the single-patch cost instead of accumulating across tiles. Volumes that already fit (<= the patch in
every dim, e.g. the CI smoke examples) run whole, unchanged. Patch/overlap are overridable via
BFRNET_PATCH / BFRNET_OVERLAP.

Reads <inp>/totalfield.nii.gz (ppm) + mask, writes <out>/localfield.nii.gz (ppm).
"""
import json
import os
import sys

import numpy as np
import nibabel as nib
import onnxruntime as ort

# Declared parameters (see algorithm.yml). Defaults tile the challenge volume into 128^3 patches with
# 32-voxel overlap (~5.3 GB peak, local field within corr 0.992 of the whole-volume result). Override
# per run: `qsm-ci run algorithms/bfrnet --set patch_size=160` (bigger = closer to whole-volume,
# more RAM), or `--set patch_size=0` to run the whole volume in one pass (needs ~19 GB for the
# challenge volume). Resolved from QSMCI_SET_<NAME> / config.json, exactly like the other subs.
PATCH_DEFAULT = 128
OVERLAP_DEFAULT = 32


def _override(name, cfg, default, cast):
    """config.json / QSMCI_SET_<NAME> override for a declared parameter, else default."""
    env = os.environ.get("QSMCI_SET_" + name.upper())
    if env is not None:
        return cast(env)
    if name in cfg and cfg[name] is not None:
        return cast(cfg[name])
    return default


def _load_cfg(inp: str) -> dict:
    p = os.path.join(inp, "config.json")
    if os.path.exists(p):
        with open(p) as fh:
            return json.load(fh)
    return {}


def _session(onnx_path: str) -> ort.InferenceSession:
    so = ort.SessionOptions()
    # Don't let the CPU memory arena grow across tiles — keep peak at the single-patch cost.
    so.enable_cpu_mem_arena = False
    return ort.InferenceSession(onnx_path, so, providers=["CPUExecutionProvider"])


def _predict(sess: ort.InferenceSession, iname: str, vol: np.ndarray) -> np.ndarray:
    """Run the net on one volume, post-padding each spatial dim to a multiple of 8 (BFRnet's 3 pooling
    levels need it) and cropping the prediction back."""
    pad = [(0, (-s) % 8) for s in vol.shape]
    out = sess.run(None, {iname: np.pad(vol, pad)[None, None].astype(np.float32)})[0][0, 0]
    return out[: vol.shape[0], : vol.shape[1], : vol.shape[2]].astype(np.float64)


def _hann1d(n: int) -> np.ndarray:
    if n == 1:
        return np.ones(1)
    return np.clip(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / (n - 1)), 1e-3, None)


def _starts(length: int, patch: int, step: int) -> list:
    """Patch start offsets covering [0, length): strided, with the last patch pinned to the end so the
    tail is fully covered."""
    if length <= patch:
        return [0]
    s = list(range(0, length - patch + 1, step))
    if s[-1] != length - patch:
        s.append(length - patch)
    return s


def predict_background(sess, iname, tfs: np.ndarray, patch: int, overlap: int) -> np.ndarray:
    """Predict the background field over `tfs`. Runs the whole volume in one pass when `patch <= 0`
    or the volume already fits in a patch; otherwise memory-bounded tiling with Hann-blended overlap."""
    D, H, W = tfs.shape
    if patch <= 0 or (D <= patch and H <= patch and W <= patch):
        return _predict(sess, iname, tfs)

    step = max(1, patch - overlap)
    pz, py, px = min(patch, D), min(patch, H), min(patch, W)
    win = np.einsum("i,j,k->ijk", _hann1d(pz), _hann1d(py), _hann1d(px))
    acc = np.zeros((D, H, W))
    wsum = np.zeros((D, H, W))
    for z in _starts(D, pz, step):
        for y in _starts(H, py, step):
            for x in _starts(W, px, step):
                patch = tfs[z:z + pz, y:y + py, x:x + px]
                bp = _predict(sess, iname, patch)
                acc[z:z + pz, y:y + py, x:x + px] += bp * win
                wsum[z:z + pz, y:y + py, x:x + px] += win
    return acc / np.maximum(wsum, 1e-9)


def main(inp: str, out: str) -> None:
    onnx_path = os.environ.get("BFRNET_ONNX", "/opt/bfrnet/BFRnet.onnx")

    tf_nii = nib.load(os.path.join(inp, "totalfield.nii.gz"))
    tfs = np.asarray(tf_nii.dataobj, dtype=np.float64)
    if tfs.ndim > 3:
        tfs = tfs[..., 0]
    mask = (np.asarray(nib.load(os.path.join(inp, "mask.nii.gz")).dataobj) > 0.5).astype(np.float64)
    tfs = tfs * mask                                     # net trained on masked total field

    cfg = _load_cfg(inp)
    patch = _override("patch_size", cfg, PATCH_DEFAULT, int)
    overlap = _override("overlap", cfg, OVERLAP_DEFAULT, int)
    print(f"BFRnet: totalfield {tfs.shape}, patch_size {patch}, overlap {overlap}", flush=True)

    sess = _session(onnx_path)
    iname = sess.get_inputs()[0].name
    bkg = predict_background(sess, iname, tfs, patch, overlap)

    local = (tfs - bkg) * mask                           # local tissue field, ppm

    os.makedirs(out, exist_ok=True)
    nib.save(nib.Nifti1Image(local.astype(np.float32), tf_nii.affine, tf_nii.header),
             os.path.join(out, "localfield.nii.gz"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/input",
         sys.argv[2] if len(sys.argv) > 2 else "/output")
