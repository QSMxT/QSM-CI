#!/usr/bin/env bash
# QSM-CI submission — NDI (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.tau // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tau $V"
  V=$(jq -r '.alpha // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
fi
# QSMxT after v10.0.0: NDI (FANSI ndi.m, astewartau/QSM.rs#222) converts the field to phase at the first echo time
# and requires the magnitude as its data weight
# (FANSI's in vivo form, min(2·mag/max, 1), of the root sum of squares of the echoes). qsmxt
# v10.0.0 takes neither.
if qsmxt invert ndi --help 2>/dev/null | grep -q -- '--field-strength'; then
  FS=$(jq -r .B0 "$IN/params.json"); TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  exec qsmxt invert ndi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
    --b0-direction $B0 --field-strength "$FS" --echo-times $TES --magnitude "$IN/magnitude.nii.gz" $SET
fi
qsmxt invert ndi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
