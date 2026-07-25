#!/usr/bin/env python3
"""QSM-CI `bfr` stage — BFRnet deep-learning background field removal (MATLAB-free, ONNX Runtime).

BFRnet is a 3D dual-frequency octave-convolution U-net that predicts the BACKGROUND field from the
total field; the local tissue field is total - background, masked. Everything is in ppm (the network
never sees TE/B0/B0_dir). This is a faithful port of the authors' MATLAB network: the trained
`BFRnet.mat` DAGNetwork was exported to ONNX with `exportONNXNetwork`, and this script reproduces the
MATLAB `recon.m` inference exactly (validated to max |Δ| = 9e-8 vs MATLAB `predict`). It replaces the
compiled-MATLAB/MCR submission — same output, ~10x less memory (no MATLAB Runtime), much smaller image.

Reads <inp>/totalfield.nii.gz (ppm) + mask, writes <out>/localfield.nii.gz (ppm).
"""
import os
import sys

import numpy as np
import nibabel as nib
import onnxruntime as ort


def main(inp: str, out: str) -> None:
    onnx_path = os.environ.get("BFRNET_ONNX", "/opt/bfrnet/BFRnet.onnx")

    tf_nii = nib.load(os.path.join(inp, "totalfield.nii.gz"))
    tfs = np.asarray(tf_nii.dataobj, dtype=np.float64)
    if tfs.ndim > 3:
        tfs = tfs[..., 0]
    mask = (np.asarray(nib.load(os.path.join(inp, "mask.nii.gz")).dataobj) > 0.5).astype(np.float64)
    tfs = tfs * mask                                     # net trained on masked total field

    # BFRnet's 3 pooling levels need dims divisible by 8 — post-pad with zeros, crop back after.
    pad = [(-s) % 8 for s in tfs.shape]
    tfp = np.pad(tfs, [(0, p) for p in pad], mode="constant")

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    bkg = sess.run(None, {iname: tfp[None, None].astype(np.float32)})[0][0, 0].astype(np.float64)
    bkg = bkg[: tfs.shape[0], : tfs.shape[1], : tfs.shape[2]]

    local = (tfs - bkg) * mask                           # local tissue field, ppm

    os.makedirs(out, exist_ok=True)
    nib.save(nib.Nifti1Image(local.astype(np.float32), tf_nii.affine, tf_nii.header),
             os.path.join(out, "localfield.nii.gz"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/input",
         sys.argv[2] if len(sys.argv) > 2 else "/output")
