#!/usr/bin/env python3
"""ROMEO field mapping — QSM-CI `field-mapping` stage.

Reads /input/{phase,magnitude}.nii.gz (multi-echo) + mask + params, writes /output/totalfield.nii.gz
(ppm). Each echo is unwrapped with ROMEO (via the bundled qsmxt engine), then a per-voxel linear fit
of unwrapped phase vs TE gives the off-resonance frequency, converted Hz -> ppm.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

GAMMA = 42.576e6  # Hz/T


def romeo_unwrap(phase_e, mag_e, mask, affine, workdir):
    """Unwrap a single 3D echo with `qsmxt unwrap romeo`; returns the unwrapped phase array."""
    pin = workdir / "phase_e.nii.gz"
    min_ = workdir / "mag_e.nii.gz"
    mkin = workdir / "mask.nii.gz"
    pout = workdir / "uw_e.nii.gz"
    nib.save(nib.Nifti1Image(phase_e.astype(np.float32), affine), pin)
    nib.save(nib.Nifti1Image(mag_e.astype(np.float32), affine), min_)
    nib.save(nib.Nifti1Image(mask.astype(np.uint8), affine), mkin)
    subprocess.run(
        ["qsmxt", "unwrap", "romeo", str(pin), "-m", str(mkin), "-o", str(pout),
         "--magnitude", str(min_)],
        check=True, stdout=subprocess.DEVNULL,
    )
    return nib.load(str(pout)).get_fdata().astype(np.float64)


def main(inp, out):
    p = json.load(open(f"{inp}/params.json"))
    TE = np.asarray(p["TE"], float)
    B0 = float(p["B0"])

    pimg = nib.load(f"{inp}/phase.nii.gz")
    phase = pimg.get_fdata().astype(np.float64)
    mag = nib.load(f"{inp}/magnitude.nii.gz").get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5
    if phase.ndim == 3:
        phase = phase[..., None]
        mag = mag[..., None]
    ne = phase.shape[3]
    if TE.size < ne:
        TE = TE[0] * np.arange(1, ne + 1)

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        unwrapped = np.stack(
            [romeo_unwrap(phase[..., e], mag[..., e], mask, pimg.affine, wd) for e in range(ne)],
            axis=-1,
        )

    # Per-voxel linear fit phi = omega*TE + c ; slope = cov(TE, phi) / var(TE)  (rad/s).
    dt = TE - TE.mean()
    phibar = unwrapped.mean(axis=3, keepdims=True)
    slope = np.sum(dt[None, None, None, :] * (unwrapped - phibar), axis=3) / np.sum(dt**2)

    field_hz = slope / (2 * np.pi)
    field_ppm = field_hz * 1e6 / (GAMMA * B0) * mask

    nib.save(nib.Nifti1Image(field_ppm.astype(np.float32), pimg.affine), f"{out}/totalfield.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
