#!/usr/bin/env bash
# Writes a chimap that is NOT on the input grid — one voxel wider on each axis. Stands in for a
# method that ignores the smoke crop and reconstructs at its own size.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
python3 - "$IN/localfield.nii.gz" "$OUT/chimap.nii.gz" <<'PY'
import sys
import nibabel as nib
import numpy as np
src = nib.load(sys.argv[1])
big = np.zeros(tuple(n + 1 for n in src.shape[:3]), "float32")
big[tuple(slice(0, n) for n in src.shape[:3])] = np.asarray(src.dataobj, "float32")
nib.save(nib.Nifti1Image(big, src.affine), sys.argv[2])
PY
