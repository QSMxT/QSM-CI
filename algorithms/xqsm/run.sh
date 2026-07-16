#!/usr/bin/env bash
# QSM-CI submission — xQSM (dipole stage), CPU-only.
#
# xQSM is a pretrained octave-convolutional, noise-regularized U-Net for dipole inversion: it takes
# the LOCAL (tissue) field and produces susceptibility. Hence stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: the QSM-CI localfield is an unwrapped frequency map already in ppm (normalized by B0). The
# xQSM in-vivo checkpoint was trained on ppm local field maps, so we pass it straight through with no
# rescaling and multiply the output susceptibility (ppm) by the mask.
#
# B0 direction / voxel size: the repo's pure-Python inference (inference.run_xqsm) operates on the
# field map directly — the network zero-pads each dim to a multiple of 8 internally and is orientation-
# agnostic; it does NOT take z_prjs or vox arguments (those belong to the MATLAB wrappers). Voxel size
# and orientation are carried by the NIfTI affine, which inference.py reads from the input and writes
# unchanged onto the output. So we only need to forward the local field + mask. $QSMCI_B0_DIR /
# $QSMCI_VOXEL_SIZE (see CONTRACT.md) are therefore not consumed by this Python path.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Force CPU-only (belt-and-braces; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"

# The xQSM repo (with baked checkpoints) lives in the image; run.sh is mounted at /algo.
XQSM_DIR="${XQSM_DIR:-/opt/xQSM}"

WORK="$(mktemp -d)"
python "$XQSM_DIR/run.py" \
  --lfs  "$IN/localfield.nii.gz" \
  --mask "$IN/mask.nii.gz" \
  --output "$WORK"

# run.py -> inference.run_xqsm writes <output>/xQSM.nii.gz. Publish it under the canonical name.
mkdir -p "$OUT"
mv "$WORK/xQSM.nii.gz" "$OUT/chimap.nii.gz"
rm -rf "$WORK"
