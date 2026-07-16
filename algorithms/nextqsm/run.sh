#!/usr/bin/env bash
# QSM-CI submission — NeXtQSM (bfr+dipole stage), CPU-only.
#
# NeXtQSM is a complete pipeline: its background-field-removal U-Net + variational-network dipole
# inversion take the TOTAL (tissue) field and produce susceptibility. Hence stage = bfr+dipole:
#   consumes  totalfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: the QSM-CI totalfield is already an unwrapped frequency map in ppm (normalized by B0), which
# is exactly what NeXtQSM expects ("unitless and scaled to ppm"). No rescaling is applied. NeXtQSM
# reads the voxel size from the NIfTI header, so we only need to pass the B0 direction for the dipole
# kernel.
#
# Acquisition parameters are injected as env vars (see CONTRACT.md):
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Force CPU-only TensorFlow (belt-and-braces; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"
export TF_CPP_MIN_LOG_LEVEL="${TF_CPP_MIN_LOG_LEVEL:-2}"

# B0 direction for the dipole kernel. Prefer the env var; fall back to params.json; default axial.
if [ -n "${QSMCI_B0_DIR:-}" ]; then
  B0_DIR="$QSMCI_B0_DIR"
elif command -v jq >/dev/null 2>&1 && [ -f "$IN/params.json" ]; then
  B0_DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"
else
  B0_DIR="0 0 1"
fi
# shellcheck disable=SC2086
set -- $B0_DIR
BX="${1:-0}"; BY="${2:-0}"; BZ="${3:-1}"

nextqsm \
  "$IN/totalfield.nii.gz" \
  "$IN/mask.nii.gz" \
  "$OUT/chimap.nii.gz" \
  --b_vec "$BX" "$BY" "$BZ"

# NeXtQSM also writes a *_BF.nii.gz (the background-removed local field). The scoring target is
# chimap.nii.gz; leave the extra file in place (harmless) — QSM-CI only reads canonical filenames.
