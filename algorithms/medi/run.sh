#!/usr/bin/env bash
# QSM-CI submission — MEDI (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
qsmxt invert medi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 --field-strength "$(jq -r .B0 "$IN/params.json")" --echo-time "$(jq -r .TE[0] "$IN/params.json")" --smv false --magnitude "$IN/magnitude.nii.gz"
