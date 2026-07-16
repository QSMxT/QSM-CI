#!/usr/bin/env bash
# QSM-CI submission — HARPERELLA (unwrap+bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# HARPERELLA operates on the first echo's phase; --te (that echo's TE) and --field-strength convert
# its tissue-phase output from radians to ppm (qsmxt >= v9.7.0).
B0=$(jq -r '.B0' "$IN/params.json")
TE=$(jq -r '.TE[0]' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --radius $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
fi
qsmxt bgremove harperella "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --te "$TE" --field-strength "$B0" $SET
