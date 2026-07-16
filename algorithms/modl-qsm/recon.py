#!/usr/bin/env python3
"""MoDL-QSM dipole-inversion runner for QSM-CI (stage = dipole).

Consumes  /input/localfield.nii.gz, /input/mask.nii.gz, /input/params.json
Produces  /output/chimap.nii.gz  (susceptibility, ppm)

MoDL-QSM (github.com/Ruimin-Feng/MoDL-QSM) is an unrolled model-based network. Its `model_test`
entry point takes the tissue/local field, the brain mask, the voxel size, and the B0 direction; it
builds the dipole kernel internally (test_tools.dipole_kernel from the B0 direction) and applies the
train-set input normalisation via the shipped NormFactor.mat.

Units. MoDL-QSM's `phi` input is the tissue field normalised to ppm (the repo's example test_data.mat
`phi` arrays span ~±0.1-0.2, i.e. ppm — not radians). QSM-CI's localfield.nii.gz is already in ppm,
so it is fed to the network unchanged. Likewise the output susceptibility is in ppm and written out
unchanged.

Normalisation (NormFactor.mat). MoDL-QSM does NOT normalise the raw input in this script — the
train-set mean/std (CosTrnMean/CosTrnStd) are baked into the Keras graph by define_generator(), which
normalises each intermediate susceptibility estimate before the CNN prior and de-normalises after
(see model/MoDL_QSM.py: `(x-CosTrnMean)/CosTrnStd` ... `x*CosTrnStd+CosTrnMean`). Because model_test
loads '../NormFactor.mat' relative to the CWD, we run from $MODL_QSM_HOME/test so the factors are
found and applied — omitting this would leave the output scale wrong.

Output. The network emits two channels: χ33 (STI-flavoured but comparable to scalar QSM) and the
field induced by the χ13/χ23 terms. We keep channel 0 (χ33) as the chimap.
"""
import json
import os
import sys

import nibabel as nib
import numpy as np
from scipy.io import savemat

IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"

MODL_HOME = os.environ.get("MODL_QSM_HOME", "/opt/MoDL-QSM")
TEST_DIR = os.path.join(MODL_HOME, "test")

# model_test() loads '../NormFactor.mat' and imports model.MoDL_QSM via a relative sys.path hack in
# test_tools.py, so the CWD must be the repo's test/ dir for both to resolve.
os.chdir(TEST_DIR)
sys.path.insert(0, TEST_DIR)
sys.path.insert(0, MODL_HOME)

from test_tools import model_test  # noqa: E402  (import after chdir/sys.path setup)

# --- Load QSM-CI inputs -------------------------------------------------------------------------
localfield_nii = nib.load(os.path.join(IN, "localfield.nii.gz"))
mask_nii = nib.load(os.path.join(IN, "mask.nii.gz"))

phi = np.asarray(localfield_nii.dataobj, dtype=np.float64)          # tissue/local field, ppm
mask = (np.asarray(mask_nii.dataobj) > 0).astype(np.float32)        # binary brain mask

# Voxel size (mm) and B0 direction (unit vector) from params.json / env vars.
params = {}
ppath = os.path.join(IN, "params.json")
if os.path.exists(ppath):
    with open(ppath) as fh:
        params = json.load(fh)


def _vec(env_name, key, default):
    env = os.environ.get(env_name)
    if env:
        return [float(v) for v in env.split()]
    if key in params and params[key] is not None:
        return [float(v) for v in params[key]]
    return list(default)


voxel_size = _vec("QSMCI_VOXEL_SIZE", "voxel_size", [1.0, 1.0, 1.0])
b0_dir = _vec("QSMCI_B0_DIR", "B0_dir", [0.0, 0.0, 1.0])

# Prefer the affine-derived voxel size when params omits it / disagrees, matching the NIfTI grid.
hdr_zooms = [float(z) for z in localfield_nii.header.get_zooms()[:3]]
if hdr_zooms and all(z > 0 for z in hdr_zooms):
    voxel_size = hdr_zooms

print("MoDL-QSM: phi", phi.shape, "voxel_size", voxel_size, "B0_dir", b0_dir, flush=True)

# --- Run the model ------------------------------------------------------------------------------
# model_dir is the committed weights; is_full_size=True runs the whole volume in one pass (the
# repo's default). model_test builds the dipole kernel from b0_dir and applies NormFactor.mat.
model_dir = os.path.join("..", "logs", "last.h5")
Y = model_test(model_dir, phi, mask, voxel_size, b0_dir, True)
Y = np.asarray(Y)

# Y is (X, Y, Z, 2): channel 0 = χ33 susceptibility (ppm), channel 1 = χ13/χ23-induced field.
chi = Y[..., 0] if Y.ndim == 4 else Y

# model_test may crop odd dimensions to even; pad χ back to the input grid so the affine matches.
if chi.shape != phi.shape:
    pad = [(0, phi.shape[i] - chi.shape[i]) for i in range(3)]
    chi = np.pad(chi, pad, mode="constant")

chi = (chi * mask).astype(np.float32)

os.makedirs(OUT, exist_ok=True)
out_path = os.path.join(OUT, "chimap.nii.gz")
# Preserve the input grid/affine (all 3D artifacts share mask.nii.gz's geometry).
nib.Nifti1Image(chi, mask_nii.affine, mask_nii.header).to_filename(out_path)
print("MoDL-QSM: wrote", out_path, chi.shape, "ppm", flush=True)
