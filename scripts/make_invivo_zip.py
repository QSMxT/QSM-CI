#!/usr/bin/env python3
"""Pack the 2016 QSM Reconstruction Challenge data into the QSM-CI in-vivo scoring layout.

Unlike the sim / χ-sep datasets (qsm-forward BIDS trees flattened by pack_dataset.py), the 2016
challenge ships as a handful of niftis, so this emits the *already-flattened* canonical layout
directly. `fetch_dataset.sh invivo` just unzips it — no BIDS packing step.

Produced zip (unzips to inputs/ + groundtruth/ at its root):

    inputs/
      mask.nii.gz          <- msk.nii.gz            (brain mask, BET eroded 5 vox)
      magnitude.nii.gz     <- magn.nii.gz           (single-echo; viewer underlay)
      params.json          <- written here
    groundtruth/
      localfield.nii.gz    <- phs_tissue.nii.gz     (LOCAL FIELD, ppm — the isolated dipole input)
      chimap.nii.gz        <- chi_cosmos.nii.gz     (primary reference, ppm)
      chimap-sti.nii.gz    <- chi_33.nii.gz         (secondary reference, ppm)
      dseg.nii.gz          <- evaluation_mask.nii.gz (optional; unused by the dipole metric set)

Only the `dipole` stage is scorable here: localfield (ppm) -> chimap (ppm), scored against COSMOS
and STI χ33. Dipole is ppm-in/ppm-out, so no TE/B0 conversion is involved anywhere; B0/TE in
params.json are for display only and do not affect scores.

Usage:
    python scripts/make_invivo_zip.py <challenge_data_dir> <out.zip>
    # e.g. .../20170327_qsm2016_recon_challenge/data  invivo_qsm2016.zip
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np

# 2016 challenge acquisition: 3T, single (transversal) orientation for the challenge; voxel size
# from spatial_res.txt. B0/TE are display-only (ppm dipole scoring ignores them); TE is a nominal
# placeholder for the single-echo GRE.
PARAMS = {
    "TE": [0.025],
    "B0": 3.0,
    "B0_dir": [0.0, 0.0, 1.0],
    "voxel_size": [1.0625, 1.0625, 1.0714286],
}

# source stem -> (dest subdir, dest name)
LAYOUT = {
    "msk":             ("inputs", "mask.nii.gz"),
    "magn":            ("inputs", "magnitude.nii.gz"),
    "phs_tissue":      ("groundtruth", "localfield.nii.gz"),
    "chi_cosmos":      ("groundtruth", "chimap.nii.gz"),
    "chi_33":          ("groundtruth", "chimap-sti.nii.gz"),
    "evaluation_mask": ("groundtruth", "dseg.nii.gz"),
}


def load(src: Path, stem: str) -> nib.Nifti1Image:
    for ext in (".nii.gz", ".nii"):
        p = src / f"{stem}{ext}"
        if p.exists():
            return nib.load(str(p))
    raise SystemExit(f"missing {stem}.nii[.gz] under {src}")


def sanity_check(data: dict[str, np.ndarray]) -> None:
    """Fail loud if the units aren't what the layout assumes (the whole point of dipole-only is that
    everything is already ppm)."""
    errs = []
    tis = data["phs_tissue"]
    if not (0.02 < np.abs(tis).max() < 1.0):
        errs.append(f"phs_tissue (localfield) max |v|={np.abs(tis).max():.4f} — expected ppm-scale "
                    "(~0.1); is it in radians?")
    for chi in ("chi_cosmos", "chi_33"):
        m = np.abs(data[chi]).max()
        if not (0.05 < m < 2.0):
            errs.append(f"{chi} max |v|={m:.4f} — expected ppm-scale (~0.3)")
    msk = data["msk"]
    if not set(np.unique(np.rint(msk[np.isfinite(msk)]))) <= {0, 1}:
        errs.append("msk is not binary {0,1}")
    if errs:
        raise SystemExit("unit sanity check failed:\n  - " + "\n  - ".join(errs))
    print("[make_invivo_zip] unit sanity check ok "
          f"(localfield |max|={np.abs(tis).max():.3f} ppm, "
          f"COSMOS |max|={np.abs(data['chi_cosmos']).max():.3f} ppm)")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, out_zip = Path(sys.argv[1]), Path(sys.argv[2])

    imgs = {stem: load(src, stem) for stem in LAYOUT}
    data = {stem: im.get_fdata(dtype=np.float64) for stem, im in imgs.items()}

    affs = [im.affine for im in imgs.values()]
    if not all(np.allclose(affs[0], a) for a in affs):
        raise SystemExit("source volumes do not share one affine grid")
    sanity_check(data)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for stem, (sub, name) in LAYOUT.items():
            dst = root / sub / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            arr = data[stem]
            if name == "dseg.nii.gz":
                arr = np.rint(arr).astype(np.int16)
            else:
                arr = arr.astype(np.float32)
            nib.save(nib.Nifti1Image(arr, imgs[stem].affine), str(dst))
        (root / "inputs" / "params.json").write_text(json.dumps(PARAMS, indent=2) + "\n")

        files = sorted(p for p in root.rglob("*") if p.is_file())
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, p.relative_to(root))

    print(f"[make_invivo_zip] wrote {out_zip} ({out_zip.stat().st_size // 1024} KB)")
    with zipfile.ZipFile(out_zip) as z:
        for i in z.infolist():
            print(f"    {i.filename:32s} {i.file_size // 1024:6d} KB")


if __name__ == "__main__":
    main()
