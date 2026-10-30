#!/usr/bin/env python3
"""Gibbs-ringing removal, run as the original: DIPY's `gibbs_removal` (Kellner et al. 2016,
local subvoxel shifts), the reference of qsm_core::utils::gibbs.

    python gibbs.py IN.nii[.gz] OUT.nii.gz [--slice-axis 2] [--n-points 3]

IN is a 3-D volume or a 4-D stack (x, y, z, volume); DIPY unrings each 2-D slice normal to
`--slice-axis` (its default 2), each volume in turn, with its default `n_points` 3, in one process.
"""
import argparse

import nibabel as nib
import numpy as np
from dipy.denoise.gibbs import gibbs_removal

ap = argparse.ArgumentParser()
ap.add_argument("inp")
ap.add_argument("out")
ap.add_argument("--slice-axis", type=int, default=2)
ap.add_argument("--n-points", type=int, default=3)
a = ap.parse_args()

img = nib.load(a.inp)
vol = np.asarray(img.dataobj, dtype=np.float64)
out = gibbs_removal(vol, slice_axis=a.slice_axis, n_points=a.n_points, inplace=False,
                    num_processes=1)
hdr = img.header.copy()
hdr.set_data_dtype(np.float64)
nib.save(nib.Nifti1Image(np.asarray(out, dtype=np.float64), img.affine, hdr), a.out)
