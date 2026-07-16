#!/usr/bin/env bash
# QSM-CI submission — NLTV (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
fi
qsmxt invert nltv "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
