#!/usr/bin/env python3
"""3-D best-path phase unwrapping, run as the original: scikit-image's `unwrap_phase`
(skimage/restoration/unwrap_3d_ljmu.c, Abdul-Rahman et al. 2007), the reference of
qsm_core::unwrap::bestpath.

    python bestpath.py PHASE.nii[.gz] OUT.nii.gz [--mask MASK.nii[.gz]] [--seed N]

PHASE is one 3-D wrapped phase volume (rad). With a mask, voxels where it is zero are masked out
(a numpy masked array, as scikit-image documents) and written as 0. `--seed` is scikit-image's
`rng`, the seed of the random reliabilities it gives border voxels (default 0, so a run is
repeatable). No other parameter: periodic boundaries are off (`wrap_around=False`), as in MRI.
"""
import argparse

import nibabel as nib
import numpy as np
from skimage.restoration import unwrap_phase

ap = argparse.ArgumentParser()
ap.add_argument("phase")
ap.add_argument("out")
ap.add_argument("--mask")
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

img = nib.load(a.phase)
phase = np.asarray(img.dataobj, dtype=np.float64)
if phase.ndim != 3:
    raise SystemExit(f"bestpath.py: expected one 3-D volume, got shape {phase.shape}")
if a.mask:
    keep = np.asarray(nib.load(a.mask).dataobj) > 0
    out = unwrap_phase(np.ma.array(phase, mask=~keep), wrap_around=False, rng=a.seed)
    out = np.ma.filled(out, 0.0)
else:
    out = unwrap_phase(phase, wrap_around=False, rng=a.seed)
hdr = img.header.copy()
hdr.set_data_dtype(np.float64)
nib.save(nib.Nifti1Image(np.asarray(out, dtype=np.float64), img.affine, hdr), a.out)
