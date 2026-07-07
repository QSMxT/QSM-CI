#!/usr/bin/env bash
# QSM-CI submission — TGV (bfr+dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.iterations // empty' "$CFG"); [ -n "$V" ] && SET="$SET --iterations $V"
  V=$(jq -r '.alpha1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha1 $V"
  V=$(jq -r '.alpha0 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha0 $V"
fi
qsmxt invert tgv "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 --field-strength "$(jq -r .B0 "$IN/params.json")" --echo-time "$(jq -r .TE[0] "$IN/params.json")" $SET
