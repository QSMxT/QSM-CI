#!/usr/bin/env python3
"""QSM-CI `dipole` stage: QSMnetME (SNU-LIST χ-separation toolbox v1.1.3, deep learning).

QSMnetME (`models/240904_QSMnet.onnx`) is the QSM network of the χ-separation toolbox, trained on
multi-echo data (Kim et al., χ-sepnet, Hum Brain Mapp 2025, §2.2.2). The toolbox runs it only
inside `chi_sepnet_general`, to make χ-sepnet's QSM channel; this entry runs that step on its own,
by the toolbox's route (chisep_route.py): the local field rotated into the training frame (B0 along
the third axis, 1 mm, interp3 'spline'), z-scored with the χ-sepnet field statistics, the network on
the whole frame, de-normalised with the COSMOS statistics, masked, and mapped back onto the acquired
grid with interp3 'spline' — the toolbox's treatment of the maps it returns — then masked.

Reads localfield.nii.gz (ppm), mask.nii.gz and params.json (B0, B0_dir); voxel sizes from the NIfTI
header. Writes chimap.nii.gz (ppm). The ppm field is converted to Hz with CF = γ·B0 and back inside
the route, as the toolbox's inputs are in Hz.
"""
import json
import os
import sys

import nibabel as nib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chisep_route as cr  # noqa: E402

GAMMA_HZ_PER_T = 42.5774806e6


def main(inp, out):
    img = nib.load(os.path.join(inp, "localfield.nii.gz"))
    field = np.asarray(img.get_fdata(), dtype=np.float64)
    mask = np.asarray(nib.load(os.path.join(inp, "mask.nii.gz")).get_fdata()) > 0.5
    with open(os.path.join(inp, "params.json")) as f:
        p = json.load(f)
    cf = GAMMA_HZ_PER_T * float(p.get("B0", 3.0))
    b0 = np.asarray(p.get("B0_dir", [0.0, 0.0, 1.0]), dtype=np.float64)
    vs = np.asarray(img.header.get_zooms()[:3], dtype=np.float64)
    nets = cr.toolbox_nets(which=("qsmnet",), threads=int(os.environ.get("QSMCI_THREADS", "0")))
    chi = cr.qsmnetme(field * cf * 1e-6, mask, b0, cf, vs, nets, norm=cr.load_norm())
    os.makedirs(out, exist_ok=True)
    hdr = img.header.copy()
    hdr.set_data_dtype(np.float32)
    nib.save(nib.Nifti1Image(chi.astype(np.float32), img.affine, hdr), os.path.join(out, "chimap.nii.gz"))
    print("qsmnetme: wrote chimap", chi.shape, flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/input", sys.argv[2] if len(sys.argv) > 2 else "/output")
