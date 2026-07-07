#!/usr/bin/env python3
import json
import os
import sys

import nibabel as nib
import numpy as np

inp, out = sys.argv[1], sys.argv[2]
img = nib.load(f"{inp}/localfield.nii.gz")
lf = img.get_fdata().astype(np.float64)
cfg = json.load(open(f"{inp}/config.json")) if os.path.exists(f"{inp}/config.json") else {}
print("CONFIG:", cfg)
scale = float(cfg.get("scale", 1.0))
nib.save(nib.Nifti1Image((lf * scale).astype(np.float32), img.affine), f"{out}/chimap.nii.gz")
