#!/usr/bin/env bash
# QSM-CI submission — MEDI (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG"); [ -n "$V" ] && SET="$SET --medi-lambda $V"
  V=$(jq -r '.percentage // empty' "$CFG"); [ -n "$V" ] && SET="$SET --medi-percentage $V"
fi
qsmxt invert medi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 --field-strength "$(jq -r .B0 "$IN/params.json")" --echo-time "$(jq -r .TE[0] "$IN/params.json")" --smv false --magnitude "$IN/magnitude.nii.gz" $SET
