#!/usr/bin/env bash
# QSM-CI submission — QSMGAN (dipole stage), CPU-only.
#
# QSMGAN is a 3D U-Net generator refined by a WGAN-GP. It maps a background-removed
# LOCAL field (in ppm) straight to susceptibility. Hence stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: QSMGAN's upstream pipeline feeds it the SEPIA local field (background-removed,
# ppm). QSM-CI's localfield.nii.gz is already that: a local field in ppm on the mask
# grid. No rescaling of the input is applied here (the model's own input_scale=100 and
# output_scale=10 / arctanh handling live in recon.py, matching the upstream config).
#
# Field POLARITY: QSM-CI's local field is simulated by qsm-forward with the dipole kernel
# D = 1/3 - kz^2/k^2. QSMGAN was trained on the OPPOSITE field convention (QSMnet-lineage
# D = kz^2/k^2 - 1/3), so feeding the QSM-CI field as-is makes the generator emit -chi
# (isolated corr/xsim came out negative: xsim=-0.030, corr=-0.716). We NEGATE the input
# local field to match the training polarity; the generator then emits correctly-signed chi
# (verified: isolated corr flips to +0.74). This is an input-convention fix, not an output negation.
#
# Inference is patch-based: 64^3 input -> 48^3 receptive-field-cropped output (i64o48).
# recon.py tiles the volume by 48^3 output patches and stitches them; see recon.py.
#
# Force CPU: no GPU at score time, and the legacy torch build runs CPU-only fine.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

export CUDA_VISIBLE_DEVICES="-1"
export QSMGAN_WEIGHTS="${QSMGAN_WEIGHTS:-/opt/qsmgan/WGAN_i64o48}"

# Code is mounted at /algo (see CONTRACT.md); weights are baked into the image.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stage a temp input dir whose localfield is negated to match QSMGAN's training polarity; other
# inputs (mask/params/magnitude) are symlinked through unchanged. recon.py reads <dir>/localfield
# and <dir>/mask, so the baked inference code is untouched (input-only, convention-matching fix).
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
for f in "$IN"/*; do
  b="$(basename "$f")"
  [ "$b" = "localfield.nii.gz" ] && continue
  ln -s "$f" "$WORK/$b"
done
python - "$IN/localfield.nii.gz" "$WORK/localfield.nii.gz" <<'PY'
import sys, numpy as np, nibabel as nib
nii = nib.load(sys.argv[1])
neg = nib.Nifti1Image(-np.asarray(nii.get_fdata(), dtype=np.float32), nii.affine, nii.header)
neg.set_data_dtype(np.float32)
nib.save(neg, sys.argv[2])
PY

python "$SCRIPT_DIR/recon.py" "$WORK" "$OUT"
