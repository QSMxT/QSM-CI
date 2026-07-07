#!/usr/bin/env python3
"""No-op background field removal baseline — QSM-CI `bfr` stage.

Passes the total field through as the local field (masked). A deliberately trivial baseline: it
quantifies how much a real BFR method buys you, and exercises the composition matrix with an
algorithm that has no background-removal at all.
"""
import sys

import nibabel as nib
import numpy as np


def main(inp, out):
    fimg = nib.load(f"{inp}/totalfield.nii.gz")
    field = fimg.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5
    local = field * mask
    nib.save(nib.Nifti1Image(local.astype(np.float32), fimg.affine), f"{out}/localfield.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
