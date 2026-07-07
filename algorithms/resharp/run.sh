#!/usr/bin/env bash
# QSM-CI submission — RESHARP (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(sed -n 's/.*"B0_dir"[^[]*\[\([^]]*\)\].*/\1/p' "$IN/params.json" | tr ',' ' ')
qsmxt bgremove resharp "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0
