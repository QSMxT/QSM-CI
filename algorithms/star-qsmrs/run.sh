#!/usr/bin/env bash
# QSM-CI submission — STAR-QSM (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
FS=$(jq -r '.B0' "$IN/params.json")
TES=$(jq -r '.TE | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.te // empty' "$CFG"); [ -n "$V" ] && SET="$SET --te $V"
  # pad: one number (every axis) or three ("12 12 12"), voxels per side.
  V=$(jq -r '.pad // empty | tostring' "$CFG")
  if [ -n "$V" ]; then
    read -r -a P <<< "$V"
    [ "${#P[@]}" -eq 1 ] && P=("${P[0]}" "${P[0]}" "${P[0]}")
    SET="$SET --pad ${P[*]}"
  fi
fi
qsmxt invert star "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 \
  --field-strength "$FS" --echo-times $TES $SET
