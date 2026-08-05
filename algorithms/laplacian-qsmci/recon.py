#!/usr/bin/env python3
"""Laplacian field mapping — QSM-CI `field-mapping` stage.

Reads /input/{phase,magnitude}.nii.gz (multi-echo) + mask + params, writes /output/totalfield.nii.gz
(ppm). Laplacian phase unwrapping per echo, then a per-voxel linear fit of unwrapped phase vs TE to
get the off-resonance frequency, converted Hz -> ppm.
"""
import json
import sys

import nibabel as nib
import numpy as np

GAMMA = 42.576e6  # Hz/T


def laplacian_unwrap(phi, vox):
    nx, ny, nz = phi.shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, vox[0])
    ky = 2 * np.pi * np.fft.fftfreq(ny, vox[1])
    kz = 2 * np.pi * np.fft.fftfreq(nz, vox[2])
    KX, KY, KZ = np.meshgrid(kx, ky, kz, indexing="ij")
    k2 = KX**2 + KY**2 + KZ**2

    def lap(x):
        return np.real(np.fft.ifftn(-k2 * np.fft.fftn(x)))

    rhs = np.cos(phi) * lap(np.sin(phi)) - np.sin(phi) * lap(np.cos(phi))
    F = np.fft.fftn(rhs)
    with np.errstate(divide="ignore", invalid="ignore"):
        G = F / (-k2)
    G[0, 0, 0] = 0.0
    return np.real(np.fft.ifftn(G))


def main(inp, out):
    p = json.load(open(f"{inp}/params.json"))
    TE = np.asarray(p["TE"], float)
    B0 = float(p["B0"])
    vox = np.asarray(p["voxel_size"], float)

    pimg = nib.load(f"{inp}/phase.nii.gz")
    phase = pimg.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5
    if phase.ndim == 3:
        phase = phase[..., None]
    ne = phase.shape[3]

    unwrapped = np.stack([laplacian_unwrap(phase[..., e], vox) for e in range(ne)], axis=-1)

    # Per-voxel linear fit phi = omega*TE + c ; slope = cov(TE, phi) / var(TE)  (rad/s).
    dt = TE - TE.mean()
    phibar = unwrapped.mean(axis=3, keepdims=True)
    slope = np.sum(dt[None, None, None, :] * (unwrapped - phibar), axis=3) / np.sum(dt**2)

    field_hz = slope / (2 * np.pi)
    field_ppm = field_hz * 1e6 / (GAMMA * B0) * mask

    nib.save(nib.Nifti1Image(field_ppm.astype(np.float32), pimg.affine), f"{out}/totalfield.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
