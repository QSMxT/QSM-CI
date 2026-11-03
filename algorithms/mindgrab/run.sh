#!/usr/bin/env bash
# QSM-CI submission: MindGrab (brain-extraction stage), the original: `brainchop --skull-strip`
# (brainchop-cli 31150c3, tinygrad, CPU) on the root-sum-of-squares combined magnitude.
#   consumes magnitude.nii.gz  ->  produces mask.nii.gz (uint8, on the magnitude's grid)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
mkdir -p "$OUT"

# brainchop and tinygrad write caches under $HOME: run from a writable copy of the baked one (the
# runner may use a read-only image and an arbitrary user).
export HOME="$(mktemp -d)"
cp -r "${BRAINCHOP_HOME:-/opt/brainchop-home}/." "$HOME/"
WORK="$(mktemp -d)"

# One 3-D magnitude: the echoes combined by root-sum-of-squares, as hd-bet-qsmci and `qsmxt mask`
# do; brainchop takes a single volume. float32, on the input's header.
python3 - "$IN/magnitude.nii.gz" "$WORK/mag.nii" <<'PY'
import sys
import nibabel as nib
import numpy as np
img = nib.load(sys.argv[1])
d = np.asarray(img.dataobj, dtype=np.float64)
if d.ndim == 4:
    d = np.sqrt(np.sum(d ** 2, axis=-1))
hdr = img.header.copy()
hdr.set_data_dtype(np.float32)
out = nib.Nifti1Image(d.astype(np.float32), img.affine, hdr)
out.header.set_xyzt_units(*img.header.get_xyzt_units())
nib.save(out, sys.argv[2])
PY

# brainchop's own pipeline: niimath -conform (256³, 1 mm), quantile normalisation, MeshNet, the
# largest 26-connected component, nearest-neighbour reslice to the input grid (`--mask`). No beam
# search (`--no-optimize`): kernel choice would otherwise depend on a timing run.
cd "$WORK"
brainchop mag.nii -o "$WORK/brain.nii.gz" --skull-strip --mask "$WORK/mask.nii.gz" --no-optimize
python3 - "$WORK/mask.nii.gz" "$OUT/mask.nii.gz" <<'PY'
import sys
import nibabel as nib
import numpy as np
img = nib.load(sys.argv[1])
m = (np.asarray(img.dataobj) > 0).astype(np.uint8)
hdr = img.header.copy()
hdr.set_data_dtype(np.uint8)
hdr.set_slope_inter(1, 0)
nib.save(nib.Nifti1Image(m, img.affine, hdr), sys.argv[2])
PY
