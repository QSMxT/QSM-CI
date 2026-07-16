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

python "$SCRIPT_DIR/recon.py" "$IN" "$OUT"
