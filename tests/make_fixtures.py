#!/usr/bin/env python3
"""Write a tiny synthetic dataset for CI smoke tests: <out>/inputs + <out>/groundtruth.

Not a real phantom — just enough for the CLI/runner/scoring plumbing. The truth chimap equals the
localfield input, so a method that copies its input scores correlation/xsim = 1.0.
"""
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/qsmci-fix")
(out / "inputs").mkdir(parents=True, exist_ok=True)
(out / "groundtruth").mkdir(parents=True, exist_ok=True)

aff = np.eye(4)
rng = np.random.default_rng(0)
field = (rng.standard_normal((16, 16, 16)) * 0.05).astype("float32")

nib.save(nib.Nifti1Image(field, aff), out / "inputs" / "localfield.nii.gz")
nib.save(nib.Nifti1Image(np.ones((16, 16, 16), "float32"), aff), out / "inputs" / "mask.nii.gz")
(out / "inputs" / "params.json").write_text(
    json.dumps({"TE": [0.004], "B0": 3.0, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
nib.save(nib.Nifti1Image(field, aff), out / "groundtruth" / "chimap.nii.gz")

print(f"fixtures -> {out}")
