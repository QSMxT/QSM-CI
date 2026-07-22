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
# Field POLARITY: QSM-CI's field is simulated by qsm-forward with the dipole kernel
# D = 1/3 - kz^2/k^2  (field = ifft(fft(chi) * D)). AutoQSM was trained on the OPPOSITE field
# convention (the QSMnet-lineage D = kz^2/k^2 - 1/3), so feeding the QSM-CI field as-is makes the
# V-Net emit -chi (isolated corr/xsim came out negative: xsim=-0.033, corr=-0.505). We therefore
# NEGATE the input field to match the training polarity; the network then emits correctly-signed chi
# (verified: isolated corr flips to +0.53). This is an input-convention fix, not an output negation.
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

# Negate the totalfield into a temp NIfTI so the baked predict.py / V-Net is untouched (input-only,
# convention-matching fix). Uses the numpy/nibabel already in the image.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
python - "$IN/totalfield.nii.gz" "$WORK/totalfield.nii.gz" <<'PY'
import sys, numpy as np, nibabel as nib
nii = nib.load(sys.argv[1])
neg = nib.Nifti1Image(-np.asarray(nii.get_fdata(), dtype=np.float32), nii.affine, nii.header)
neg.set_data_dtype(np.float32)
nib.save(neg, sys.argv[2])
PY

# Pass the mounted brain mask so the whole-head V-Net output is zeroed outside the brain (AutoQSM
# does no brain extraction). Cosmetic for the viewer — scoring is already mask-restricted.
python "$HERE/predict.py" \
  "$WORK/totalfield.nii.gz" \
  "$OUT/chimap.nii.gz" \
  "$IN/mask.nii.gz"
