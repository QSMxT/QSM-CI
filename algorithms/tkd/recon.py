#!/usr/bin/env python3
"""TKD dipole inversion — QSM-CI `dipole` stage.

Reads /input/localfield.nii.gz (ppm) + mask + params, writes /output/chimap.nii.gz (ppm).
Thresholded k-space division: chi = F^-1{ F{field} / D_thr }, with the dipole kernel D thresholded
away from its magic-angle zeros.
"""
import json
import sys

import nibabel as nib
import numpy as np


def dipole_kernel(shape, vox, b0):
    kx = np.fft.fftfreq(shape[0], vox[0])
    ky = np.fft.fftfreq(shape[1], vox[1])
    kz = np.fft.fftfreq(shape[2], vox[2])
    KX, KY, KZ = np.meshgrid(kx, ky, kz, indexing="ij")
    k2 = KX**2 + KY**2 + KZ**2
    kb = KX * b0[0] + KY * b0[1] + KZ * b0[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        D = 1.0 / 3.0 - (kb**2) / k2
    D[0, 0, 0] = 0.0
    return D


def main(inp, out):
    p = json.load(open(f"{inp}/params.json"))
    b0 = np.array(p["B0_dir"], float)
    b0 /= np.linalg.norm(b0)
    vox = np.array(p["voxel_size"], float)

    fimg = nib.load(f"{inp}/localfield.nii.gz")
    field = fimg.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5

    thr = 0.2
    D = dipole_kernel(field.shape, vox, b0)
    Dt = np.where(np.abs(D) < thr, np.sign(D) * thr, D)
    Dt[Dt == 0] = thr
    chi = np.real(np.fft.ifftn(np.fft.fftn(field) / Dt)) * mask

    nib.save(nib.Nifti1Image(chi.astype(np.float32), fimg.affine), f"{out}/chimap.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
