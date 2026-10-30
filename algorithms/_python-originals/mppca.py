#!/usr/bin/env python3
"""Marchenko-Pastur PCA denoising, run as the original: DIPY's `mppca` (Veraart et al. 2016,
eigenvalue path), the reference of qsm_core::utils::denoise.

    python mppca.py IN.nii[.gz] OUT.nii.gz [--mask MASK.nii[.gz]] [--patch-radius 2]

IN is a 4-D stack (x, y, z, volume), e.g. the multi-echo magnitude. DIPY's defaults otherwise:
`pca_method='eig'`, overlapping patches averaged.
"""
import argparse

import nibabel as nib
import numpy as np
from dipy.denoise.localpca import mppca

ap = argparse.ArgumentParser()
ap.add_argument("inp")
ap.add_argument("out")
ap.add_argument("--mask")
ap.add_argument("--patch-radius", type=int, default=2)
a = ap.parse_args()

img = nib.load(a.inp)
arr = np.asarray(img.dataobj, dtype=np.float64)
mask = (np.asarray(nib.load(a.mask).dataobj) > 0) if a.mask else None
out = mppca(arr, mask=mask, patch_radius=a.patch_radius, pca_method="eig",
            out_dtype=np.float64)
hdr = img.header.copy()
hdr.set_data_dtype(np.float64)
nib.save(nib.Nifti1Image(np.asarray(out, dtype=np.float64), img.affine, hdr), a.out)
