#!/usr/bin/env bash
# QSM-CI submission — RESHARP (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --radius $V"
  V=$(jq -r '.tik_reg // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tik-reg $V"
fi
qsmxt bgremove resharp "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0 $SET
