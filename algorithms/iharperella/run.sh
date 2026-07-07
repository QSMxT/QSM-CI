#!/usr/bin/env bash
# QSM-CI submission — iHARPERELLA (unwrap+bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --radius $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
fi
qsmxt bgremove iharperella "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" $SET
