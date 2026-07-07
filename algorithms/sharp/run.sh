#!/usr/bin/env bash
# QSM-CI submission — SHARP (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.threshold // empty' "$CFG"); [ -n "$V" ] && SET="$SET --sharp-threshold $V"
  V=$(jq -r '.radius_factor // empty' "$CFG"); [ -n "$V" ] && SET="$SET --sharp-radius-factor $V"
fi
qsmxt bgremove sharp "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0 $SET
