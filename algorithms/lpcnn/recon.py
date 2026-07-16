#!/usr/bin/env python3
"""Prepare LPCNN inference inputs for QSM-CI (dipole stage, single orientation).

run.sh calls this to turn the QSM-CI artifacts into the exact inputs LPCNN/inference.py
expects, then invokes inference.py itself. This script:

  1. Reads /input/localfield.nii.gz (ppm), /input/mask.nii.gz, /input/params.json.
  2. Writes a phase NIfTI in Hz (see Units below) — the file inference.py reads as "phase".
  3. Generates the dipole-kernel .npy (see Dipole below) from params.json.
  4. Writes the phase_file / dipole_file / mask_file .txt lists inference.py consumes.

Two facts pinned against LPCNN source:

Units. LPCNN/inference.py loads the phase file and computes `phase / (tesla * gamma)` with
  gamma = 42.57747892 (MHz/T). The LPCNN dataset "phase" files are the LOCAL FIELD in Hz, so
  that division yields the ppm-scaled field the physics operator (D * y) and the pretrained
  ppm gt_mean/gt_std expect. QSM-CI provides the local field already in ppm, so we undo the
  division by writing the phase file in Hz: Hz = ppm * tesla * gamma. (verified: dataset
  phase std ~2.8; /(7*gamma) -> ~0.009, matching the ppm cosmos target scale.)

Dipole. lib/model/lpcnn/lpcnn.py does `np.load(dipole_path)` and multiplies it against the
  ortho FFT of the field (DC at array corner). The committed .mat kernels, after
  data/to_numpy.py's swapaxes(0,1), equal
      D = 1/3 - (k . B0)^2 / |k|^2 , k from np.fft.fftfreq(n, d=voxel), D[0,0,0]=0
  in (x,y,z) order (verified: max|Cs - D| ~ 9e-8 on a demo case). We generate exactly that.
"""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

GAMMA = 42.57747892  # MHz/T, matches LPCNN inference.py


def make_dipole(matrix, voxel, b0_dir):
    b0 = np.asarray(b0_dir, dtype=float)
    b0 = b0 / np.linalg.norm(b0)
    kx, ky, kz = np.meshgrid(
        np.fft.fftfreq(matrix[0], d=voxel[0]),
        np.fft.fftfreq(matrix[1], d=voxel[1]),
        np.fft.fftfreq(matrix[2], d=voxel[2]),
        indexing="ij",
    )
    k2 = kx**2 + ky**2 + kz**2
    kB = kx * b0[0] + ky * b0[1] + kz * b0[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        D = 1.0 / 3.0 - (kB**2) / k2
    D[0, 0, 0] = 0.0
    return D.astype(np.float64)


def main(in_dir, work_dir, tesla):
    in_dir, work_dir = Path(in_dir), Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    params = json.loads((in_dir / "params.json").read_text())
    b0_dir = params.get("B0_dir", [0.0, 0.0, 1.0])
    voxel = params.get("voxel_size")

    field_img = nib.load(str(in_dir / "localfield.nii.gz"))
    field_ppm = field_img.get_fdata()
    if voxel is None:
        voxel = [float(z) for z in field_img.header.get_zooms()[:3]]
    matrix = field_ppm.shape[:3]

    # ppm -> Hz so inference.py's internal /(tesla*gamma) recovers the ppm field.
    field_hz = field_ppm * (float(tesla) * GAMMA)
    phase_path = work_dir / "phase.nii.gz"
    nib.Nifti1Image(field_hz.astype(np.float32), field_img.affine, field_img.header).to_filename(
        str(phase_path)
    )

    dipole_path = work_dir / "dipole.npy"
    np.save(str(dipole_path), make_dipole(matrix, voxel, b0_dir))

    (work_dir / "phase_data.txt").write_text(str(phase_path) + "\n")
    (work_dir / "dipole_data.txt").write_text(str(dipole_path) + "\n")
    (work_dir / "mask_data.txt").write_text(str((in_dir / "mask.nii.gz").resolve()) + "\n")
    print("prepared LPCNN inputs in", work_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
