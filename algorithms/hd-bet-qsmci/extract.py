#!/usr/bin/env python3
"""HD-BET brain extraction — QSM-CI `brain-extraction` stage.

Reads /input/magnitude.nii.gz (multi-echo), combines echoes by root-sum-of-squares into one
magnitude, runs the HD-BET CNN to segment the brain, and writes /output/mask.nii.gz — a 3D uint8
binary mask (0/1) on the magnitude's grid. RSS gives HD-BET a higher-SNR combined image than any
single echo.

Runs on CPU by default (`-device cpu`); set QSMCI_GPU=1 to run on CUDA. HD-BET's model weights are
baked into the image at build time, since there is no network at run time.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np


def _combine_echoes(img):
    """Return a 3D magnitude from a (possibly 4D multi-echo) input via root-sum-of-squares
    across echoes: sqrt(sum_e mag_e^2). A 3D input is returned unchanged."""
    data = img.get_fdata().astype(np.float64)
    if data.ndim == 4:
        data = np.sqrt(np.sum(data ** 2, axis=-1))
    return data.astype(np.float32)


def _find_mask(out_dir: Path, stem: str) -> Path:
    """Locate the mask HD-BET produced. HD-BET v2 names it `<stem>_bet.nii.gz` (older builds use
    `*_mask.nii.gz`); glob for either so we don't depend on one exact suffix."""
    for pattern in (f"{stem}_bet.nii.gz", f"{stem}*mask*.nii.gz", "*_bet.nii.gz", "*mask*.nii.gz"):
        hits = sorted(out_dir.glob(pattern))
        if hits:
            return hits[0]
    raise SystemExit(f"HD-BET produced no mask file in {out_dir} (found: {[p.name for p in out_dir.iterdir()]})")


def main(inp, out):
    mag_img = nib.load(f"{inp}/magnitude.nii.gz")
    mag = _combine_echoes(mag_img)
    affine = mag_img.affine

    device = "cuda" if os.environ.get("QSMCI_GPU") == "1" else "cpu"

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        mag_in = wd / "mag.nii.gz"
        nib.save(nib.Nifti1Image(mag, affine), str(mag_in))

        out_dir = wd / "hdbet"
        out_dir.mkdir()
        bet_out = out_dir / "brain.nii.gz"
        # HD-BET v2 discards the mask unless --save_bet_mask; it writes it beside -o as
        # `<stem>_bet.nii.gz` (here brain_bet.nii.gz). --no_bet_image skips the skull-stripped
        # image since we only want the mask.
        subprocess.run(
            ["hd-bet", "-i", str(mag_in), "-o", str(bet_out), "-device", device,
             "--disable_tta", "--save_bet_mask", "--no_bet_image"],
            check=True,
        )

        mask_path = _find_mask(out_dir, "brain")
        mask = nib.load(str(mask_path)).get_fdata() > 0.5

    nib.save(nib.Nifti1Image(mask.astype(np.uint8), affine), f"{out}/mask.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
