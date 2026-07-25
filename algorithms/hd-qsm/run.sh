#!/usr/bin/env bash
# QSM-CI submission — HD-QSM (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.alpha_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha-l2 $V"
  V=$(jq -r '.mu1_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --mu1-l2 $V"
  V=$(jq -r '.max_iter_l1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter-l1 $V"
  V=$(jq -r '.max_iter_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter-l2 $V"
fi
qsmxt invert hdqsm "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
