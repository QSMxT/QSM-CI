#!/usr/bin/env python3
"""QSM-CI `chi-separation` stage: χ-sepnet (SNU-LIST χ-separation toolbox v1.1.3, deep learning).

The authors' full route, `chi_sepnet_general` (`Chisep_script.m`:177-194, the `resgen = false`
branch), reproduced in chisep_route.py: the local field, R2′ and mask rotated into the training frame
(B0 along the third axis, 1 mm), the QSM channel made there by the toolbox's own QSMnetME, χ-sepnet
on the whole frame, and χ+ / χ− mapped back onto the acquired grid. χ-sepnet-R2′ (the stage gives a
measured R2′); the toolbox's χ-sepnet-R2* variant (R2PRIMEnet inside the route) is
`chisep_route.route(..., have_r2prime=False)`.

The entry no longer reads chimap.nii.gz: the toolbox makes its own QSM. (Its first version fed the
stage's χ map as the QSM channel and ran the network on the acquired grid in 192×192×128 patches.)

Reads localfield.nii.gz (ppm), r2prime.nii.gz (Hz), mask.nii.gz and params.json (B0, B0_dir); voxel
sizes from the NIfTI header. Writes chi-para.nii.gz (χ+) and chi-dia.nii.gz (|χ−|), ppm. Dr = 114
Hz/ppm unless config.json sets Dr (`qsm-ci run chisepnet --set Dr=…`).
"""
import json
import os
import sys

import nibabel as nib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chisep_route as cr  # noqa: E402

GAMMA_HZ_PER_T = 42.5774806e6
DEFAULT_DR = 114.0   # Chisep_script.m:186 (the networks were trained on COSMOS maps)


def read_dr(inp):
    p = os.path.join(inp, "config.json")
    if os.path.exists(p):
        with open(p) as f:
            v = json.load(f).get("Dr")
        if v is not None:
            return float(v)
    return DEFAULT_DR


def main(inp, out):
    img = nib.load(os.path.join(inp, "localfield.nii.gz"))
    field = np.asarray(img.get_fdata(), dtype=np.float64)
    r2p = np.asarray(nib.load(os.path.join(inp, "r2prime.nii.gz")).get_fdata(), dtype=np.float64)
    mask = np.asarray(nib.load(os.path.join(inp, "mask.nii.gz")).get_fdata()) > 0.5
    with open(os.path.join(inp, "params.json")) as f:
        p = json.load(f)
    cf = GAMMA_HZ_PER_T * float(p.get("B0", 3.0))
    b0 = np.asarray(p.get("B0_dir", [0.0, 0.0, 1.0]), dtype=np.float64)
    vs = np.asarray(img.header.get_zooms()[:3], dtype=np.float64)
    nets = cr.toolbox_nets(which=("qsmnet", "xsepnet"), threads=int(os.environ.get("QSMCI_THREADS", "0")))
    xp, xn, _, _, _ = cr.route(field * cf * 1e-6, r2p, mask, read_dr(inp), b0, cf, vs, True, nets,
                               norm=cr.load_norm())
    os.makedirs(out, exist_ok=True)
    hdr = img.header.copy()
    hdr.set_data_dtype(np.float32)
    for name, v in (("chi-para", xp), ("chi-dia", xn)):
        nib.save(nib.Nifti1Image(v.astype(np.float32), img.affine, hdr), os.path.join(out, f"{name}.nii.gz"))
    print("chi-sepnet: wrote chi-para/chi-dia", xp.shape, flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/input", sys.argv[2] if len(sys.argv) > 2 else "/output")
