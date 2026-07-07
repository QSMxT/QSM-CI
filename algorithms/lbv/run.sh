#!/usr/bin/env bash
# QSM-CI submission — LBV (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
qsmxt bgremove lbv "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0
