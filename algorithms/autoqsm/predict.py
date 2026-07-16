#!/usr/bin/env python3
"""AutoQSM inference for QSM-CI (bfr+dipole span): totalfield.nii.gz -> chimap.nii.gz.

AutoQSM (Wei et al., NeuroImage 2019) is a single-step V-Net that maps a total field map directly to
susceptibility with NO brain extraction and NO separate background-field removal. Its published
`test.py` hardcodes a `.mat`-file workflow (key `x_input`) and a `results/` output dir; this wrapper
reuses its network definition (`vnet`) and its patch-based sliding-window inference (`data_predict`,
which zero-/edge-pads to a multiple of shift=24 and stitches 64^3 -> 32^3 patches) but plumbs the
QSM-CI NIfTI artifacts through instead.

Units. QSM-CI's totalfield.nii.gz is an unwrapped field map already in **ppm** (normalized by B0).
AutoQSM's `x_input` is likewise a field map in ppm — the shipped test_data/0.mat `x_input` is a dense
whole-head map with values ~[-0.9, 0.5], std ~0.11, exactly the scale of a 3T total field in ppm
(and dense with no zero background, consistent with "no brain extraction"). So we feed the totalfield
voxels through unchanged. The network's final activation is tanh, so its output susceptibility is in
ppm as well; we write it out unchanged. No Hz/rad rescaling is applied.

Usage:  predict.py <totalfield.nii.gz> <chimap.nii.gz>
"""
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")   # force CPU
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import nibabel as nib

# Make AutoQSM's own modules (model.py, util.py) importable from the baked repo.
AUTOQSM_HOME = os.environ.get("AUTOQSM_HOME", "/opt/AutoQSM")
sys.path.insert(0, os.path.join(AUTOQSM_HOME, "code"))

from model import vnet            # noqa: E402  (AutoQSM V-Net definition)
from util import data_predict     # noqa: E402  (AutoQSM patch inference / stitching)

WEIGHTS = os.path.join(AUTOQSM_HOME, "models", "vnet", "model_final_1.hdf5")
INPUT_PATCH_SHAPE = [64, 64, 64]
OUTPUT_PATCH_SHAPE = [32, 32, 32]


def main(in_path, out_path):
    nii = nib.load(in_path)
    field = np.asarray(nii.get_fdata(), dtype=np.float32)   # totalfield, ppm
    if field.ndim != 3:
        raise ValueError("expected a 3D totalfield, got shape {}".format(field.shape))

    # Build the V-Net and load AutoQSM's pretrained weights (single-channel field -> chi).
    model = vnet(INPUT_PATCH_SHAPE, OUTPUT_PATCH_SHAPE, 1)
    model.load_weights(WEIGHTS)

    # data_predict zero-/edge-pads to a multiple of shift=24 and runs the 64^3 -> 32^3 sliding window,
    # returning the susceptibility map cropped back to the input grid.
    chi, _patches = data_predict(model, field, INPUT_PATCH_SHAPE, OUTPUT_PATCH_SHAPE)
    chi = np.asarray(chi, dtype=np.float32)                 # susceptibility, ppm

    # Preserve the input grid / voxel size / affine (QSM-CI 3D artifacts all share the mask grid).
    out = nib.Nifti1Image(chi, nii.affine, nii.header)
    out.set_data_dtype(np.float32)
    nib.save(out, out_path)
    print("AutoQSM: wrote {} (shape {})".format(out_path, chi.shape))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: predict.py <totalfield.nii.gz> <chimap.nii.gz>")
    main(sys.argv[1], sys.argv[2])
