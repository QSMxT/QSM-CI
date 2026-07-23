#!/usr/bin/env python3
"""QSM-CI wrapper for MoDIP dipole inversion (stage = dipole), CPU by default.

Consumes  /input/localfield.nii.gz, /input/mask.nii.gz, /input/params.json
Produces  /output/chimap.nii.gz  (susceptibility, ppm)

MoDIP (Xiong, Gao, Sun, NeuroImage 2024; github.com/sunhongfu/MoDIP) is an UNSUPERVISED /
untrained method: it loads NO pretrained weights. A small 3D U-Net (deep image prior) is optimized
per-subject at inference time so that its output susceptibility, pushed through the QSM dipole
forward model, matches the input local field (plus a gradient-domain regularizer). Because of this,
each run performs `epoch_num` optimization iterations and is expensive — see README RUNTIME/GPU
CAVEAT.

We reuse the repo's own optimization loop, `inference.run_modip`, which:
  * loads the local field NIfTI (get_fdata),
  * builds its OWN foreground mask as (data != 0) and crops the zero background bounding box,
  * builds the dipole kernel internally from `z_prjs` (B0 direction) and `vox` (voxel size) via
    utils.handy.generate_dipole,
  * optimizes ModelBasedDIPNet for `epoch_num` iterations (Adam, StepLR),
  * de-means the final susceptibility over the foreground, and
  * writes the result on the INPUT NIfTI affine.

Units. QSM-CI's localfield.nii.gz is the tissue/local field already in ppm (normalized by B0), which
is exactly MoDIP's expected local-field input (its `--input_type phi` / `is_field` local field). It
is fed unchanged and the output susceptibility is in ppm, written unchanged.

Device. run_modip picks cuda if torch.cuda.is_available() else cpu. run.sh sets
CUDA_VISIBLE_DEVICES=-1 to force CPU under CI (like the other subs). Set it otherwise for a GPU run.

B0 direction / voxel size come from params.json / QSMCI_* env vars, matching the other submissions.

ASSUMPTIONS (see README):
  * localfield is in ppm (per CONTRACT.md) — no unit rescale.
  * MoDIP's internal mask = (localfield != 0). We additionally intersect with the QSM-CI mask when
    writing, so voxels outside the provided brain mask are zeroed.
  * B0_dir defaults to [0,0,1] and voxel_size falls back to the NIfTI header zooms.
"""
import json
import os
import sys

import numpy as np
import nibabel as nib

IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"

MODIP_HOME = os.environ.get("MODIP_HOME", "/opt/MoDIP")
# inference.py imports `from models...` / `from utils...` relative to its own dir; add repo to path.
sys.path.insert(0, MODIP_HOME)

from inference import run_modip  # noqa: E402  (import after sys.path setup)


def _load_params():
    params = {}
    ppath = os.path.join(IN, "params.json")
    if os.path.exists(ppath):
        with open(ppath) as fh:
            params = json.load(fh)
    return params


def _vec(env_name, key, params, default):
    env = os.environ.get(env_name)
    if env:
        return [float(v) for v in env.split()]
    if key in params and params[key] is not None:
        return [float(v) for v in params[key]]
    return list(default)


def _override(name, params_cfg, default, cast):
    """config.json / QSMCI_SET_<NAME> override for a declared parameter, else default."""
    env = os.environ.get("QSMCI_SET_" + name.upper())
    if env is not None:
        return cast(env)
    if name in params_cfg and params_cfg[name] is not None:
        return cast(params_cfg[name])
    return default


def main():
    localfield_path = os.path.join(IN, "localfield.nii.gz")
    mask_path = os.path.join(IN, "mask.nii.gz")

    lfs_img = nib.load(localfield_path)
    mask = (np.asarray(nib.load(mask_path).dataobj) > 0).astype(np.float32)

    params = _load_params()

    voxel_size = _vec("QSMCI_VOXEL_SIZE", "voxel_size", params, [1.0, 1.0, 1.0])
    b0_dir = _vec("QSMCI_B0_DIR", "B0_dir", params, [0.0, 0.0, 1.0])
    # Prefer the affine-derived voxel size when it is well-defined (matches the NIfTI grid).
    hdr_zooms = [float(z) for z in lfs_img.header.get_zooms()[:3]]
    if hdr_zooms and all(z > 0 for z in hdr_zooms):
        voxel_size = hdr_zooms

    # Optional overrides for declared parameters (config.json / QSMCI_SET_*).
    cfg = {}
    cfgp = os.path.join(IN, "config.json")
    if os.path.exists(cfgp):
        with open(cfgp) as fh:
            cfg = json.load(fh)
    epoch_num = _override("epoch_num", cfg, 500, int)
    lr = _override("lr", cfg, 5e-4, float)
    base = _override("base", cfg, 32, int)

    print(
        f"MoDIP: localfield {lfs_img.shape}, voxel_size {voxel_size}, B0_dir {b0_dir}, "
        f"epoch_num {epoch_num}, lr {lr}, base {base}",
        flush=True,
    )

    os.makedirs(OUT, exist_ok=True)

    # run_modip loads the field, builds the dipole from b0_dir+vox, optimizes the DIP for epoch_num
    # iterations on the available device, and writes <output>/MoDIP.nii.gz on the input affine.
    qsm_path = run_modip(
        lfs_nii_path=localfield_path,
        vox=list(voxel_size),
        z_prjs=list(b0_dir),
        epoch_num=epoch_num,
        lr=lr,
        base=base,
        crop_background=True,
        output_dir=OUT,
    )

    # Reload MoDIP's output, intersect with the QSM-CI brain mask, and write to the canonical
    # chimap.nii.gz filename on the INPUT affine/header (voxel size + orientation preserved).
    chi_img = nib.load(qsm_path)
    chi = np.asarray(chi_img.get_fdata(), dtype=np.float32)
    if chi.shape != mask.shape:
        raise RuntimeError(
            f"MoDIP output shape {chi.shape} != mask shape {mask.shape}; cannot mask/align."
        )
    chi = (chi * mask).astype(np.float32)

    out_path = os.path.join(OUT, "chimap.nii.gz")
    nib.Nifti1Image(chi, lfs_img.affine, lfs_img.header).to_filename(out_path)
    print("MoDIP: wrote", out_path, chi.shape, "ppm", flush=True)


if __name__ == "__main__":
    main()
