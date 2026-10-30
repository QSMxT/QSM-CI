#!/usr/bin/env bash
# QSM-CI submission — SHARP (bfr stage) via QSMxT / QSM.rs.
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
  V=$(jq -r '.threshold // empty' "$CFG"); [ -n "$V" ] && SET="$SET --threshold $V"
  V=$(jq -r '.radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --radius $V"
  # sepia (default) or qsmjl, for the sharp-qsmjl parity pair (qsmxt after v10.0.0,
  # QSMxT/QSMxT#460; an older qsmxt refuses the flag).
  V=$(jq -r '.variant // empty' "$CFG"); [ -n "$V" ] && SET="$SET --variant $V"
fi
qsmxt bgremove sharp "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0 $SET
