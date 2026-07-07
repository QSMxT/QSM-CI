#!/usr/bin/env bash
# QSM-CI submission — RTS (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.delta // empty' "$CFG"); [ -n "$V" ] && SET="$SET --rts-delta $V"
  V=$(jq -r '.mu // empty' "$CFG"); [ -n "$V" ] && SET="$SET --rts-mu $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --rts-max-iter $V"
fi
qsmxt invert rts "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
