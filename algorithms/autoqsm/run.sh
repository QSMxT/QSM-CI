#!/usr/bin/env bash
# QSM-CI submission — AutoQSM (bfr+dipole span), CPU-only.
#
# AutoQSM is a single-step V-Net that maps the TOTAL field map straight to susceptibility, with NO
# brain extraction and NO separate background-field removal (Wei et al., NeuroImage 2019). Hence
# stage = bfr+dipole:
#   consumes  totalfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
# (The mask is mounted by the platform for this span but AutoQSM does not require it — it operates on
# the whole head, which is the whole point of "without brain extraction".)
#
# Units: the QSM-CI totalfield is an unwrapped field map already in ppm (normalized by B0), which is
# exactly the scale AutoQSM's `x_input` expects (its shipped test_data is a dense whole-head field map
# with values ~[-0.9, 0.5] ppm). The V-Net output (tanh) is susceptibility in ppm. No Hz/rad/ppm
# rescaling is applied. predict.py handles NIfTI<->array and preserves the mask grid / affine.
#
# Acquisition parameters are injected as env vars (see CONTRACT.md); AutoQSM needs none of them (it
# has no dipole-kernel orientation input — orientation is baked into the trained weights).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Force CPU-only TensorFlow (belt-and-braces; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"
export TF_CPP_MIN_LOG_LEVEL="${TF_CPP_MIN_LOG_LEVEL:-2}"

# predict.py lives beside this script (mounted read-only at /algo); the AutoQSM code + weights are
# baked in the image at $AUTOQSM_HOME (default /opt/AutoQSM).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python "$HERE/predict.py" \
  "$IN/totalfield.nii.gz" \
  "$OUT/chimap.nii.gz"
