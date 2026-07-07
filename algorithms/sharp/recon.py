#!/usr/bin/env python3
"""SHARP background field removal — QSM-CI `bfr` stage.

Reads /input/totalfield.nii.gz (ppm) + mask + params, writes /output/localfield.nii.gz (ppm).
Sophisticated Harmonic Artifact Reduction for Phase data: convolve with an SMV kernel to annihilate
harmonic (background) fields inside an eroded mask, then deconvolve by truncated k-space division.
"""
import json
import sys

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_erosion


def smv_ft(shape, vox, radius_mm):
    """FT of (delta - normalized sphere) — the SMV annihilation kernel."""
    centers = [s // 2 for s in shape]
    grids = np.ogrid[tuple(slice(0, s) for s in shape)]
    dist2 = sum(((g - c) * v) ** 2 for g, c, v in zip(grids, centers, vox))
    sphere = (dist2 <= radius_mm**2).astype(np.float64)
    sphere /= sphere.sum()
    ker = -sphere
    ker[tuple(centers)] += 1.0
    return np.fft.fftn(np.fft.ifftshift(ker))


def main(inp, out):
    p = json.load(open(f"{inp}/params.json"))
    vox = np.array(p["voxel_size"], float)

    fimg = nib.load(f"{inp}/totalfield.nii.gz")
    field = fimg.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5

    radius = 5.0  # mm
    thr = 0.05
    Sk = smv_ft(field.shape, vox, radius)

    # erode mask by the SMV radius (in voxels)
    rv = int(round(radius / min(vox)))
    struct = np.ones((2 * rv + 1,) * 3, bool)
    eroded = binary_erosion(mask, structure=struct)

    filtered = eroded * np.real(np.fft.ifftn(Sk * np.fft.fftn(field * mask)))
    inv = np.zeros_like(Sk)
    np.divide(1.0, Sk, out=inv, where=np.abs(Sk) > thr)  # truncated (TSVD) deconvolution
    local = eroded * np.real(np.fft.ifftn(inv * np.fft.fftn(filtered)))

    nib.save(nib.Nifti1Image(local.astype(np.float32), fimg.affine), f"{out}/localfield.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
