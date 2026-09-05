#!/usr/bin/env python3
"""HD-BET brain extraction — QSM-CI `brain-extraction` stage.

Reads /input/magnitude.nii.gz (multi-echo), combines echoes by root-sum-of-squares into one
magnitude, runs the HD-BET CNN to segment the brain, and writes /output/mask.nii.gz — a 3D uint8
binary mask (0/1) on the magnitude's grid. RSS gives HD-BET a higher-SNR combined image than any
single echo.

Optionally trims the result with a signal-gated erosion (see `_signal_erode`), off by default and
configured through /input/config.json (`erode_threshold`, `erode_depth_cap`, `erode_bias_sigma`,
`erode_min_cc`) — the standard qsm-ci `--set NAME=VALUE` parameter path.

Runs on CPU by default (`-device cpu`); set QSMCI_GPU=1 to run on CUDA. HD-BET's model weights are
baked into the image at build time, since there is no network at run time.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage


def _combine_echoes(img):
    """Return a 3D magnitude from a (possibly 4D multi-echo) input via root-sum-of-squares
    across echoes: sqrt(sum_e mag_e^2). A 3D input is returned unchanged."""
    data = img.get_fdata().astype(np.float64)
    if data.ndim == 4:
        data = np.sqrt(np.sum(data ** 2, axis=-1))
    return data.astype(np.float32)


def _signal_erode(mask, rss, threshold, depth_cap, bias_sigma, min_cc, glob=0):
    """Strip only LOW-SIGNAL BOUNDARY voxels from `mask`, to a bounded depth.

    Around the sinuses and skull base, T2* dropout leaves mask voxels with no usable signal; the
    field there is unreliable and leaks background-field artefact into QSM. A global erosion only
    suppresses that by peeling healthy cortex just as hard. This peels iteratively, but each pass
    removes only boundary voxels that are below the signal gate — so it eats inward through the
    dropout territory and halts as soon as it meets real signal.

    Two corrections that the naive version gets wrong:

    * **Receive-coil bias.** Raw RSS is dim at the vertex simply because it is far from the receive
      coils. Thresholding it against a global median therefore flags healthy vertex cortex and
      misses the skull base. Dividing the RSS by its own mask-normalised gaussian-smoothed self
      (scale `bias_sigma`) removes that profile, after which the gate lands where it should.

    * **Depth cap.** Sulcal and interhemispheric-fissure CSF is genuinely low-signal *and*
      connected all the way inward, so an uncapped peel follows it and carves fjords tens of voxels
      deep into healthy cortex. `depth_cap` bounds removal depth by construction, independent of
      path. The distance transform is computed on a PADDED mask so that a brain touching the FOV
      face (common inferiorly — exactly the region of interest) is measured as being at the
      surface, not as deep interior.

    Returns the eroded boolean mask.
    """
    mask = mask.astype(bool)
    rss = ndimage.gaussian_filter(rss.astype(np.float32), 1.0)
    # `glob` plain erosions first (a bright one-voxel skull/CSF sliver is invisible to a signal
    # gate); depth and the coil-bias estimate stay referenced to the ORIGINAL HD-BET surface.

    # divide out the receive-coil sensitivity profile (mask-normalised, so the estimate is not
    # dragged down by the zeros outside the brain)
    num = ndimage.gaussian_filter(np.where(mask, rss, 0), bias_sigma)
    den = ndimage.gaussian_filter(mask.astype(np.float32), bias_sigma)
    rel = rss / np.maximum(num / np.maximum(den, 1e-6), 1e-6)

    low = rel < threshold * float(np.median(rel[mask]))
    if depth_cap is not None:
        # pad so the FOV face counts as outside the brain, not as an interior plateau
        depth = ndimage.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1, 1:-1]
        low &= depth <= depth_cap

    eroded = ndimage.binary_erosion(mask, iterations=glob) if glob else mask.copy()
    for _ in range(max(int(depth_cap or 0) + 2, 40)):
        boundary = eroded & ~ndimage.binary_erosion(eroded)
        drop = boundary & low
        if not drop.any():
            break
        eroded &= ~drop

    eroded = ndimage.binary_fill_holes(eroded)          # never leave an enclosed cavity
    lab, n = ndimage.label(eroded)
    if n > 1:
        sizes = np.bincount(lab.ravel())[1:]
        keep = np.flatnonzero(sizes >= min(min_cc, sizes.max()))
        eroded = np.isin(lab, keep + 1)
    return eroded


def _config(inp):
    """Parameter overrides from /input/config.json (absent when the caller passed no --set)."""
    path = Path(inp) / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


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

    cfg = _config(inp)
    threshold = float(cfg.get("erode_threshold", 0.0) or 0.0)
    if threshold > 0:
        before = int(mask.sum())
        mask = _signal_erode(
            mask, mag,
            threshold=threshold,
            depth_cap=int(cfg.get("erode_depth_cap", 5)),
            bias_sigma=float(cfg.get("erode_bias_sigma", 12.0)),
            min_cc=int(cfg.get("erode_min_cc", 1000)),
            glob=int(cfg.get("erode_global", 0)),
        )
        print(f"signal-gated erosion (threshold {threshold}, depth cap "
              f"{cfg.get('erode_depth_cap', 5)}): {before} -> {int(mask.sum())} voxels "
              f"({100 * mask.sum() / max(before, 1):.1f}%)")

    nib.save(nib.Nifti1Image(mask.astype(np.uint8), affine), f"{out}/mask.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
