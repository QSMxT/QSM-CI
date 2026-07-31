#!/usr/bin/env bash
# QSM-CI submission — TFI (bfr+dipole stage) via QSMxT / QSM.rs.
# Preconditioned total field inversion: total field -> susceptibility, doing its own background removal.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# TFI takes the total field in ppm directly (like NDI — no radians conversion; the QSM-CI contract's
# totalfield is already ppm and `qsmxt invert tfi` consumes ppm). Magnitude (provided by the
# bfr+dipole stage) is used for the SNR data weight + morphology mask.
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Absent -> qsm-core
# TfiParams defaults (lambda 7.5e-5, precond 30) — honest, non-dataset-tuned.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG");  [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.precond // empty' "$CFG"); [ -n "$V" ] && SET="$SET --precond $V"
fi

qsmxt invert tfi "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 $MAG $SET
